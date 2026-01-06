-- SQLite schema for meter annotation storage
-- Apply with: sqlite3 annotations.db < schema.sql

CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Source identification
    source_client TEXT NOT NULL,
    source_reading_id INTEGER NOT NULL,
    image_url TEXT NOT NULL,

    -- Detections as JSON array, each element:
    -- {"class_label": 0|1|2, "obb": [x1,y1,x2,y2,x3,y3,x4,y4], "annotator_reading": int|null}
    -- class_label: 0=cold_water, 1=hot_water, 2=electricity
    -- Empty array [] means no meters present
    detections TEXT NOT NULL DEFAULT '[]',

    -- Metadata
    annotated_by TEXT NOT NULL,
    annotated_at TEXT NOT NULL DEFAULT (datetime('now')),

    -- Prevent duplicate annotations for same source image
    UNIQUE(source_client, source_reading_id)
);

-- Index for checking if an image has been annotated
CREATE INDEX IF NOT EXISTS idx_annotations_source
ON annotations(source_client, source_reading_id);
