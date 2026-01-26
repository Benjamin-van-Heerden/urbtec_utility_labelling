import json
import random
import sqlite3
from pathlib import Path
from typing import Any

import mysql.connector
from mysql.connector.cursor_cext import CMySQLCursorDict

from env_settings import (
    ENV_SETTINGS,
    SOURCE_CLIENTS,
    TARGET_DISTRIBUTION,
    SourceClient,
)
from utils.models.annotation import (
    Annotation,
    ClassDistribution,
    SourceReading,
)

# Local SQLite database path
LOCAL_DB_PATH = Path(__file__).parent.parent / "annotations.db"
SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"


def init_local_db() -> None:
    """Initialize the local SQLite database with schema."""
    with open(SCHEMA_PATH, "r") as f:
        schema = f.read()

    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.executescript(schema)
    conn.close()


def get_local_connection() -> sqlite3.Connection:
    """Get a connection to the local SQLite database."""
    if not LOCAL_DB_PATH.exists():
        init_local_db()
    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_class_distribution() -> ClassDistribution:
    """Get the current distribution of annotated classes."""
    conn = get_local_connection()
    cursor = conn.cursor()

    # Get all detections JSON and count classes
    cursor.execute("SELECT detections FROM annotations")
    rows = cursor.fetchall()
    conn.close()

    water_count = 0
    electricity_count = 0
    no_meter_count = 0

    for row in rows:
        detections = json.loads(row["detections"])
        if not detections:
            no_meter_count += 1
        else:
            for det in detections:
                class_label = det["class_label"]
                if class_label == 0:
                    water_count += 1
                elif class_label == 1:
                    electricity_count += 1

    return ClassDistribution(
        water_count=water_count,
        electricity_count=electricity_count,
        no_meter_count=no_meter_count,
    )


def get_annotated_reading_ids(source_client: str) -> set[int]:
    """Get all reading IDs that have already been annotated for a client."""
    conn = get_local_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT source_reading_id FROM annotations WHERE source_client = :source_client",
        {"source_client": source_client},
    )

    ids = {row["source_reading_id"] for row in cursor.fetchall()}
    conn.close()
    return ids


def save_annotation(annotation: Annotation) -> None:
    """Save an annotation to the local database."""
    conn = get_local_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO annotations (
            source_client, source_reading_id, image_url, detections, annotated_by
        ) VALUES (
            :source_client, :source_reading_id, :image_url, :detections, :annotated_by
        )
        """,
        {
            "source_client": annotation.source_client,
            "source_reading_id": annotation.source_reading_id,
            "image_url": annotation.image_url,
            "detections": annotation.detections_to_json(),
            "annotated_by": annotation.annotated_by,
        },
    )

    conn.commit()
    conn.close()


def get_annotation_count() -> int:
    """Get total number of annotations."""
    conn = get_local_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM annotations")
    count = cursor.fetchone()["count"]
    conn.close()
    return count


# Source database functions


class SourceDBCursor:
    """Context manager for source MySQL database connection."""

    def __init__(self, client: SourceClient):
        self.client = client
        self.connection: Any = None
        self.cursor: Any = None

    def __enter__(self) -> CMySQLCursorDict:
        self.connection = mysql.connector.connect(
            host=ENV_SETTINGS.source_db_host,
            port=ENV_SETTINGS.source_db_port,
            user=ENV_SETTINGS.source_db_user,
            password=ENV_SETTINGS.source_db_password,
            database=self.client.db_name,
            ssl_disabled=True,
            autocommit=True,
        )
        self.cursor = self.connection.cursor(cursor_class=CMySQLCursorDict)
        assert self.cursor is not None and isinstance(self.cursor, CMySQLCursorDict)
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()


def get_all_annotated_reading_ids() -> dict[str, set[int]]:
    """Get all annotated reading IDs grouped by client."""
    conn = get_local_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT source_client, source_reading_id FROM annotations")
    rows = cursor.fetchall()
    conn.close()

    result: dict[str, set[int]] = {}
    for row in rows:
        client = row["source_client"]
        if client not in result:
            result[client] = set()
        result[client].add(row["source_reading_id"])

    return result


def select_target_utility_type(distribution: ClassDistribution) -> str:
    """
    Select which utility type to prioritize based on current distribution vs target.

    Uses a probabilistic approach weighted by how far each type is from its target.
    """
    total = distribution.water_count + distribution.electricity_count

    if total == 0:
        # No annotations yet, pick randomly weighted by target distribution
        r = random.random()
        if r < TARGET_DISTRIBUTION["water"]:
            return "water"
        else:
            return "electricity"

    # Calculate current proportions
    current = {
        "water": distribution.water_count / total,
        "electricity": distribution.electricity_count / total,
    }

    # Calculate how far below target each type is (negative means over target)
    deficits = {
        utility_type: TARGET_DISTRIBUTION[utility_type] - current[utility_type]
        for utility_type in TARGET_DISTRIBUTION
    }

    # Only consider types that are below target
    positive_deficits = {k: v for k, v in deficits.items() if v > 0}

    if not positive_deficits:
        # All types at or above target, pick randomly by target weights
        r = random.random()
        if r < TARGET_DISTRIBUTION["water"]:
            return "water"
        else:
            return "electricity"

    # Weight selection by deficit size
    total_deficit = sum(positive_deficits.values())
    r = random.random() * total_deficit
    cumulative = 0.0
    for utility_type, deficit in positive_deficits.items():
        cumulative += deficit
        if r <= cumulative:
            return utility_type

    # Fallback
    return list(positive_deficits.keys())[0]


def select_client_for_utility_type(utility_type: str) -> SourceClient:
    """
    Select a client that has the given utility type.

    All clients have both water and electricity meters.
    """
    return random.choice(SOURCE_CLIENTS)


def fetch_random_reading() -> tuple[SourceReading, str] | None:
    """
    Fetch a random meter reading from one of the source databases.

    Selects utility type based on target distribution, then picks a client
    that has that type, and fetches a random reading.

    Returns:
        Tuple of (SourceReading, client_name) or None if no readings found
    """
    distribution = get_class_distribution()
    target_utility = select_target_utility_type(distribution)

    # Get all annotated IDs grouped by client
    annotated_by_client = get_all_annotated_reading_ids()

    # Try each client in random order until we find a reading
    clients_to_try = SOURCE_CLIENTS.copy()
    random.shuffle(clients_to_try)

    for client in clients_to_try:
        excluded_ids = annotated_by_client.get(client.name, set())

        reading = fetch_reading_from_client(
            client=client,
            utility_type=target_utility,
            excluded_ids=excluded_ids,
        )

        if reading is not None:
            return (reading, client.name)

    # If target utility not found, try any utility type
    for client in clients_to_try:
        excluded_ids = annotated_by_client.get(client.name, set())

        reading = fetch_reading_from_client(
            client=client,
            utility_type=None,  # Any type
            excluded_ids=excluded_ids,
        )

        if reading is not None:
            return (reading, client.name)

    return None


def fetch_reading_from_client(
    client: SourceClient,
    utility_type: str | None = None,
    excluded_ids: set[int] | None = None,
) -> SourceReading | None:
    """
    Fetch a random meter reading from a specific client database.

    Args:
        client: The client to fetch from
        utility_type: If specified, only fetch this utility type
        excluded_ids: Set of reading IDs to exclude (already annotated)

    Returns:
        A SourceReading or None if no suitable readings found
    """
    excluded_ids = excluded_ids or set()

    # Build the exclusion clause
    exclusion_clause = ""
    if excluded_ids:
        ids_str = ",".join(str(id) for id in list(excluded_ids)[:10000])
        exclusion_clause = f"AND mr.id NOT IN ({ids_str})"

    # Utility type filter
    # Note: source DB still has 'cold_water' and 'hot_water' - we map both to 'water'
    if utility_type == "water":
        utility_filter = "AND mh.utility_type IN ('cold_water', 'hot_water')"
    elif utility_type == "electricity":
        utility_filter = "AND mh.utility_type = 'electricity'"
    else:
        utility_filter = (
            "AND mh.utility_type IN ('cold_water', 'hot_water', 'electricity')"
        )

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
          {utility_filter}
          {exclusion_clause}
        ORDER BY RAND()
        LIMIT 1
    """

    with SourceDBCursor(client) as cursor:
        cursor.execute(query)
        row = cursor.fetchone()

    if row is None:
        return None

    # Map source utility types to our simplified types
    source_utility = row["utility_type"]
    if source_utility in ("cold_water", "hot_water"):
        mapped_utility = "water"
    else:
        mapped_utility = source_utility

    return SourceReading(
        reading_id=row["reading_id"],
        meter_no=row["meter_no"],
        utility_type=mapped_utility,
        image_url=row["image_url"],
        reading_new=row["reading_new"],
        reading_old=row["reading_old"],
    )
