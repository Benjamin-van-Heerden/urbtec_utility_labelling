---
created_at: '2026-02-26T12:26:09.260905'
username: benjamin_van_heerden
---
# Work Log - Unclassified Image Discovery Pipeline

## Overarching Goals

The trained YOLO OBB model fails to detect certain meter types that aren't represented in the training data. We needed a way to systematically find these undetected images across all clients, queue them for labelling, and integrate that queue into the Streamlit labelling app so annotators can focus on filling the model's blind spots.

## What Was Accomplished

### 1. Discovery Script (`scripts/find_unclassified.py`)

Created a script that sweeps across all client databases to find meter images the model can't detect:

- Dynamically discovers all client databases by querying the API database (`databases` table), rather than relying on hardcoded client lists
- Validates each client DB has `meter_readings` and `meter_history` tables
- Fetches random meter readings from the last year across all valid clients
- Downloads each image, runs YOLO inference at a low confidence threshold (0.15)
- Images with zero detections are added to `unclassified_queue.json`
- All scanned image IDs tracked in `scanned_ids.json` to avoid duplicate work across runs
- Saves state on each find (ctrl-c safe)
- 2s sleep on failed downloads to handle rate limiting

Usage: `uv run python scripts/find_unclassified.py --target 100`

### 2. Streamlit UI: Labelling Mode Selector

Added a radio button to the labelling page with two modes:

- **Random sample** (default) — existing distribution-balanced random fetching
- **Unclassified only** — pops images from `unclassified_queue.json`

When in unclassified mode, shows the remaining queue count. The rest of the annotation flow (canvas, submit, save to SQLite) works unchanged since the queue entries map directly to `SourceReading`.

### 3. Queue Helper Functions (`utils/database.py`)

- `get_unclassified_queue_size()` — reads queue file and returns count
- `pop_unclassified_reading()` — pops first entry, rewrites file, returns `(SourceReading, client_name)`

### 4. Environment Settings

Added `api_database` property to `Settings` that returns the correct API database name based on environment (`mobixhep_urbtec_api` for QA, `mobixenn_api` for prod).

## Key Files Affected

- `env_settings.py` — Added `api_database` property to `Settings`
- `scripts/find_unclassified.py` — New discovery script
- `utils/database.py` — Added `get_unclassified_queue_size()` and `pop_unclassified_reading()`
- `pages/1_🏷️_Meter_Labelling.py` — Added mode selector radio, split `load_new_image` into `_load_from_unclassified_queue` and `_load_random_image`
- `.gitignore` — Added `scanned_ids.json` and `unclassified_queue.json`

## What Comes Next

- Run the discovery script on the production server with a larger target (e.g. `--target 200`)
- Have annotators label the unclassified queue via the new "Unclassified only" mode
- Fetch updated annotations locally, retrain model, export improved weights
- Repeat the discovery/label/retrain cycle to progressively close coverage gaps
- Commit and deploy these changes to the production server
