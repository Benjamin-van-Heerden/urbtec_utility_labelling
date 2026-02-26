---
created_at: '2026-02-26T14:08:10.130502'
username: benjamin_van_heerden
---
# Work Log - File Locking for Unclassified Queue

## Overarching Goals

Add file locking to `unclassified_queue.json` so that `find_unclassified.py` can run in the background while the Streamlit labelling app concurrently pops entries from the same queue without data loss or corruption.

## What Was Accomplished

### 1. Shared File Lock Helper (`utils/file_lock.py`)

Created a new module with:
- `queue_lock()` — context manager using `fcntl.flock()` (exclusive advisory lock) on `unclassified_queue.json.lock`
- `read_queue()` / `write_queue()` — shared read/write helpers for the queue JSON file

### 2. Updated Discovery Script (`scripts/find_unclassified.py`)

- Removed local `load_unclassified_queue` / `save_unclassified_queue` functions, replaced with shared `queue_lock` + `read_queue` / `write_queue` from `utils.file_lock`
- The script no longer holds the full queue in memory for the entire run. Each time it finds an unclassified image, it acquires the lock, re-reads the current queue from disk, appends the new entry, and writes back. This prevents overwriting entries that the Streamlit consumer popped in the meantime.

### 3. Updated Streamlit Queue Consumer (`utils/database.py`)

- `get_unclassified_queue_size()` and `pop_unclassified_reading()` now acquire the file lock before reading/writing the queue file

### 4. Updated `.gitignore`

- Added `unclassified_queue.json.lock` to ignore list

## Key Files Affected

- `utils/file_lock.py` — New shared file lock module
- `scripts/find_unclassified.py` — Replaced in-memory queue with lock-protected read-append-write per find
- `utils/database.py` — Queue read/pop now uses file lock
- `.gitignore` — Added lock file

## What Comes Next

- Deploy these changes to the production server
- Run the discovery script in the background while annotators use the Streamlit app
- Continue the discovery/label/retrain cycle to close model coverage gaps
