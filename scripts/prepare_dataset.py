"""
Prepare YOLO OBB dataset from annotations database.

Downloads images and creates label files in YOLO OBB format.
Output structure:
    datasets/meter_obb/
    ├── data.yaml
    ├── images/
    │   ├── train/
    │   └── val/
    └── labels/
        ├── train/
        └── val/

Resumable: skips already downloaded images.
"""

import asyncio
import json
import logging
import random
import sqlite3
from pathlib import Path

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "annotations.db"
DATASET_DIR = PROJECT_ROOT / "datasets" / "meter_obb"

CLASS_NAMES = {0: "water", 1: "electricity"}
TRAIN_SPLIT = 0.8
CONCURRENT_DOWNLOADS = 3
MAX_RETRIES = 5
BASE_DELAY = 2.0


def load_annotations() -> list[dict]:
    """Load all annotations with detections from database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, source_client, source_reading_id, image_url, detections
        FROM annotations
        WHERE detections != '[]'
    """)

    rows = cursor.fetchall()
    conn.close()

    annotations = []
    for row in rows:
        annotations.append(
            {
                "id": row["id"],
                "source_client": row["source_client"],
                "source_reading_id": row["source_reading_id"],
                "image_url": row["image_url"],
                "detections": json.loads(row["detections"]),
            }
        )

    return annotations


def create_label_content(detections: list[dict]) -> str:
    """Convert detections to YOLO OBB label format."""
    lines: list[str] = []
    for det in detections:
        class_id = det["class_label"]
        obb = det["obb"]
        line = f"{class_id} {obb[0]} {obb[1]} {obb[2]} {obb[3]} {obb[4]} {obb[5]} {obb[6]} {obb[7]}"
        lines.append(line)
    return "\n".join(lines)


def get_image_filename(annotation: dict) -> str:
    """Generate unique filename for an image."""
    return f"{annotation['source_client']}_{annotation['source_reading_id']}.jpg"


async def download_image(
    client: httpx.AsyncClient,
    url: str,
    dest_path: Path,
    semaphore: asyncio.Semaphore,
) -> bool:
    """Download a single image with retry and exponential backoff."""
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                dest_path.write_bytes(response.content)
                return True
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    delay = BASE_DELAY * (2**attempt)
                    log.warning(
                        f"Rate limited, retrying in {delay:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    await asyncio.sleep(delay)
                    continue
                log.error(f"Failed to download {url}: {e}")
                return False
            except Exception as e:
                log.error(f"Failed to download {url}: {e}")
                return False
        log.error(f"Exhausted retries for {url}")
        return False


async def download_all_images(
    annotations: list[dict],
    split_assignments: dict[int, str],
) -> dict[int, bool]:
    """Download all images with rate limiting. Skips already downloaded."""
    semaphore = asyncio.Semaphore(CONCURRENT_DOWNLOADS)
    results: dict[int, bool] = {}

    skipped = 0
    to_download: list[tuple[dict, Path]] = []

    for ann in annotations:
        split = split_assignments[ann["id"]]
        dest_dir = DATASET_DIR / "images" / split
        dest_path = dest_dir / get_image_filename(ann)

        if dest_path.exists():
            results[ann["id"]] = True
            skipped += 1
        else:
            to_download.append((ann, dest_path))

    if skipped > 0:
        log.info(f"Skipping {skipped} already downloaded images")

    if not to_download:
        log.info("All images already downloaded")
        return results

    log.info(f"Downloading {len(to_download)} images...")

    async with httpx.AsyncClient() as client:
        for i, (ann, dest_path) in enumerate(to_download):
            success = await download_image(
                client, ann["image_url"], dest_path, semaphore
            )
            results[ann["id"]] = success
            if (i + 1) % 20 == 0:
                log.info(f"Progress: {i + 1}/{len(to_download)}")

    return results


def create_data_yaml():
    """Create YOLO dataset configuration file."""
    yaml_content = f"""# YOLO OBB Dataset - Meter Detection
path: {DATASET_DIR.resolve()}
train: images/train
val: images/val

names:
  0: water
  1: electricity
"""
    yaml_path = DATASET_DIR / "data.yaml"
    yaml_path.write_text(yaml_content)
    log.info(f"Created {yaml_path}")


def setup_directories():
    """Create dataset directory structure."""
    for split in ["train", "val"]:
        (DATASET_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (DATASET_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)
    log.info(f"Created directory structure at {DATASET_DIR}")


def assign_splits(annotations: list[dict]) -> dict[int, str]:
    """Assign annotations to train/val splits."""
    random.seed(42)
    shuffled = annotations.copy()
    random.shuffle(shuffled)

    split_idx = int(len(shuffled) * TRAIN_SPLIT)
    assignments = {}

    for i, ann in enumerate(shuffled):
        assignments[ann["id"]] = "train" if i < split_idx else "val"

    train_count = sum(1 for s in assignments.values() if s == "train")
    val_count = len(assignments) - train_count
    log.info(f"Split: {train_count} train, {val_count} val")

    return assignments


def create_labels(
    annotations: list[dict],
    split_assignments: dict[int, str],
    download_results: dict[int, bool],
):
    """Create label files for successfully downloaded images."""
    created = 0
    for ann in annotations:
        if not download_results.get(ann["id"], False):
            continue

        split = split_assignments[ann["id"]]
        label_dir = DATASET_DIR / "labels" / split
        label_filename = get_image_filename(ann).replace(".jpg", ".txt")
        label_path = label_dir / label_filename

        content = create_label_content(ann["detections"])
        label_path.write_text(content)
        created += 1

    log.info(f"Created {created} label files")


async def main():
    log.info("Loading annotations from database...")
    annotations = load_annotations()
    log.info(f"Found {len(annotations)} annotations with detections")

    setup_directories()

    split_assignments = assign_splits(annotations)

    log.info("Downloading images...")
    download_results = await download_all_images(annotations, split_assignments)

    successful = sum(1 for v in download_results.values() if v)
    log.info(f"Successfully downloaded/found {successful}/{len(annotations)} images")

    log.info("Creating label files...")
    create_labels(annotations, split_assignments, download_results)

    create_data_yaml()

    log.info("Dataset preparation complete!")
    log.info(f"Dataset location: {DATASET_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
