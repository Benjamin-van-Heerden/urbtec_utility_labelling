"""
Find meter images that the trained YOLO model cannot detect.

Sweeps across all client databases, fetches random meter readings from the last
year, runs inference, and collects images where the model returns no detections.
These are likely meter types not represented in the training data.

Usage:
    uv run python scripts/find_unclassified.py --target 100
    uv run python scripts/find_unclassified.py --target 50 --model runs/meter_obb/weights/best.pt
    uv run python scripts/find_unclassified.py --target 200 --conf 0.15
"""

import argparse
import json
import logging
import random
import tempfile
import time
from io import BytesIO
from pathlib import Path

import httpx
import mysql.connector
from mysql.connector.cursor_cext import CMySQLCursorDict
from PIL import Image
from ultralytics import YOLO

from env_settings import ENV_SETTINGS, SourceClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_MODEL_PATH = PROJECT_ROOT / "runs" / "meter_obb" / "weights" / "best.pt"
SCANNED_IDS_PATH = PROJECT_ROOT / "scanned_ids.json"
UNCLASSIFIED_QUEUE_PATH = PROJECT_ROOT / "unclassified_queue.json"


def load_scanned_ids() -> set[str]:
    if SCANNED_IDS_PATH.exists():
        with open(SCANNED_IDS_PATH) as f:
            return set(json.load(f))
    return set()


def save_scanned_ids(scanned: set[str]) -> None:
    with open(SCANNED_IDS_PATH, "w") as f:
        json.dump(sorted(scanned), f)


def load_unclassified_queue() -> list[dict]:
    if UNCLASSIFIED_QUEUE_PATH.exists():
        with open(UNCLASSIFIED_QUEUE_PATH) as f:
            return json.load(f)
    return []


def save_unclassified_queue(queue: list[dict]) -> None:
    with open(UNCLASSIFIED_QUEUE_PATH, "w") as f:
        json.dump(queue, f, indent=2)


def get_all_client_databases() -> list[SourceClient]:
    conn = mysql.connector.connect(
        host=ENV_SETTINGS.source_db_host,
        port=ENV_SETTINGS.source_db_port,
        user=ENV_SETTINGS.source_db_user,
        password=ENV_SETTINGS.source_db_password,
        database=ENV_SETTINGS.api_database,
        ssl_disabled=True,
    )
    cursor: CMySQLCursorDict = conn.cursor(cursor_class=CMySQLCursorDict)  # type: ignore

    cursor.execute("SELECT client_name, dbname FROM `databases`")
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return [
        SourceClient(name=row["client_name"], db_name=row["dbname"]) for row in rows
    ]  # type: ignore


def validate_client(client: SourceClient) -> bool:
    try:
        conn = mysql.connector.connect(
            host=ENV_SETTINGS.source_db_host,
            port=ENV_SETTINGS.source_db_port,
            user=ENV_SETTINGS.source_db_user,
            password=ENV_SETTINGS.source_db_password,
            database=client.db_name,
            ssl_disabled=True,
        )
        cursor = conn.cursor()

        for table in ["meter_readings", "meter_history"]:
            cursor.execute(f"SHOW TABLES LIKE '{table}'")
            if not cursor.fetchone():
                cursor.close()
                conn.close()
                return False

        cursor.close()
        conn.close()
        return True
    except Exception:
        return False


def fetch_random_reading(
    client: SourceClient,
    scanned: set[str],
) -> dict | None:
    excluded_keys = {
        k.split("_", 1)[1] for k in scanned if k.startswith(f"{client.name}_")
    }
    exclusion_clause = ""
    if excluded_keys:
        ids_str = ",".join(excluded_keys)
        exclusion_clause = f"AND mr.id NOT IN ({ids_str})"

    query = f"""
        SELECT mr.id AS reading_id,
               mr.meter_no,
               mh.utility_type,
               mr.reading_new,
               mr.reading_old,
               CONCAT('https://urbion-mobi.com/image/', mr.site, '/', mr.reading_date, '/', mr.file_name) AS image_url
        FROM meter_readings mr
        LEFT JOIN meter_history mh ON mr.meter_no = mh.meter_no
        WHERE mr.site IS NOT NULL
          AND mr.reading_date IS NOT NULL
          AND mr.file_name IS NOT NULL
          AND mr.file_name != ''
          AND mr.file_name NOT LIKE '%NOFILE%'
          AND mh.utility_type IN ('cold_water', 'hot_water', 'electricity')
          AND mr.reading_date >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
          {exclusion_clause}
        ORDER BY RAND()
        LIMIT 1
    """

    try:
        conn = mysql.connector.connect(
            host=ENV_SETTINGS.source_db_host,
            port=ENV_SETTINGS.source_db_port,
            user=ENV_SETTINGS.source_db_user,
            password=ENV_SETTINGS.source_db_password,
            database=client.db_name,
            ssl_disabled=True,
            autocommit=True,
        )
        cursor: CMySQLCursorDict = conn.cursor(cursor_class=CMySQLCursorDict)  # type: ignore
        cursor.execute(query)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
    except Exception as e:
        log.warning(f"Failed to query {client.name}: {e}")
        return None

    if row is None:
        return None

    utility_type = row["utility_type"]
    if utility_type in ("cold_water", "hot_water"):
        utility_type = "water"

    reading_new = row["reading_new"]
    reading_old = row["reading_old"]

    return {
        "source_client": client.name,
        "source_reading_id": int(str(row["reading_id"])),
        "image_url": row["image_url"],
        "utility_type": utility_type,
        "meter_no": str(row["meter_no"]),
        "reading_new": float(str(reading_new)) if reading_new is not None else None,
        "reading_old": float(str(reading_old)) if reading_old is not None else None,
    }


def download_image(url: str) -> Path | None:
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()

            image = Image.open(BytesIO(response.content))
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            image.save(tmp.name)
            return Path(tmp.name)
    except Exception:
        return None


def make_key(reading: dict) -> str:
    return f"{reading['source_client']}_{reading['source_reading_id']}"


def main():
    parser = argparse.ArgumentParser(description="Find unclassified meter images")
    parser.add_argument(
        "--target",
        type=int,
        required=True,
        help="Number of unclassified images to find",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=str(DEFAULT_MODEL_PATH),
        help="Path to YOLO model weights",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.15,
        help="Confidence threshold — detections below this are ignored (default: 0.15)",
    )
    args = parser.parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        log.error(f"Model not found: {model_path}")
        return

    log.info(f"Loading model from {model_path}")
    model = YOLO(str(model_path))

    log.info("Discovering client databases...")
    all_clients = get_all_client_databases()
    log.info(f"Found {len(all_clients)} client databases, validating...")

    valid_clients = [c for c in all_clients if validate_client(c)]
    log.info(f"{len(valid_clients)} valid clients with meter data")

    if not valid_clients:
        log.error("No valid client databases found")
        return

    scanned = load_scanned_ids()
    queue = load_unclassified_queue()
    found = 0
    scanned_this_run = 0
    failed_downloads = 0
    max_consecutive_failures = 50

    log.info(
        f"Starting scan — target: {args.target}, "
        f"previously scanned: {len(scanned)}, "
        f"existing queue: {len(queue)}"
    )

    consecutive_failures = 0

    while found < args.target:
        client = random.choice(valid_clients)
        reading = fetch_random_reading(client, scanned)

        if reading is None:
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                log.warning(
                    f"Hit {max_consecutive_failures} consecutive failures to fetch readings. "
                    "Possibly exhausted available readings."
                )
                break
            continue

        key = make_key(reading)
        scanned.add(key)
        scanned_this_run += 1
        consecutive_failures = 0

        image_path = download_image(reading["image_url"])
        if image_path is None:
            failed_downloads += 1
            time.sleep(2)
            continue

        try:
            results = model.predict(
                source=str(image_path),
                conf=args.conf,
                verbose=False,
            )

            has_detections = False
            for r in results:
                if r.obb is not None and r.obb.cls is not None and len(r.obb.cls) > 0:
                    has_detections = True
                    break

            if not has_detections:
                queue.append(reading)
                found += 1
                log.info(
                    f"[{found}/{args.target}] Unclassified: {key} "
                    f"(utility_type={reading['utility_type']}, client={reading['source_client']})"
                )

                save_scanned_ids(scanned)
                save_unclassified_queue(queue)

        except Exception as e:
            log.warning(f"Inference failed for {key}: {e}")
        finally:
            image_path.unlink(missing_ok=True)

        if scanned_this_run % 100 == 0:
            save_scanned_ids(scanned)
            log.info(
                f"Progress: scanned {scanned_this_run} this run, "
                f"found {found}/{args.target} unclassified, "
                f"{failed_downloads} failed downloads"
            )

    save_scanned_ids(scanned)
    save_unclassified_queue(queue)

    log.info(
        f"Done. Scanned {scanned_this_run} images this run. "
        f"Found {found} unclassified. "
        f"Total scanned: {len(scanned)}. "
        f"Queue size: {len(queue)}. "
        f"Failed downloads: {failed_downloads}."
    )


if __name__ == "__main__":
    main()
