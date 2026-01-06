import json
import sqlite3
from pathlib import Path
from typing import Any

import mysql.connector
from mysql.connector.cursor_cext import CMySQLCursorDict

from env_settings import ENV_SETTINGS
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

    cold_water_count = 0
    hot_water_count = 0
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
                    cold_water_count += 1
                elif class_label == 1:
                    hot_water_count += 1
                elif class_label == 2:
                    electricity_count += 1

    return ClassDistribution(
        cold_water_count=cold_water_count,
        hot_water_count=hot_water_count,
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

    def __init__(self):
        self.connection: Any = None
        self.cursor: Any = None

    def __enter__(self) -> CMySQLCursorDict:
        self.connection = mysql.connector.connect(
            host=ENV_SETTINGS.source_db_host,
            port=ENV_SETTINGS.source_db_port,
            user=ENV_SETTINGS.source_db_user,
            password=ENV_SETTINGS.source_db_password,
            database=ENV_SETTINGS.source_db_name,
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


def fetch_random_reading(
    prefer_electricity: bool = False,
    excluded_ids: set[int] | None = None,
) -> SourceReading | None:
    """
    Fetch a random meter reading from the source database.

    Args:
        prefer_electricity: If True, prefer electricity readings to balance dataset
        excluded_ids: Set of reading IDs to exclude (already annotated)

    Returns:
        A SourceReading or None if no suitable readings found
    """
    excluded_ids = excluded_ids or set()

    # Build the exclusion clause
    exclusion_clause = ""
    if excluded_ids:
        # SQLite/MySQL can handle large IN clauses, but we'll limit to recent exclusions
        # For very large sets, consider a different approach
        ids_str = ",".join(str(id) for id in list(excluded_ids)[:10000])
        exclusion_clause = f"AND mr.id NOT IN ({ids_str})"

    # Determine utility type filter based on balance needs
    if prefer_electricity:
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
        ORDER BY mr.reading_date DESC, RAND()
        LIMIT 1
    """

    with SourceDBCursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()

    if row is None:
        return None

    return SourceReading(
        reading_id=row["reading_id"],
        meter_no=row["meter_no"],
        utility_type=row["utility_type"],
        image_url=row["image_url"],
        reading_new=row["reading_new"],
        reading_old=row["reading_old"],
    )
