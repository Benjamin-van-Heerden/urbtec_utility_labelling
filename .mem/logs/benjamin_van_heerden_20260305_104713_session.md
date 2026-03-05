---
created_at: '2026-03-05T10:47:13.390821'
username: benjamin_van_heerden
---
# Work Log - Unclassified Queue Skip/Reset Fixes

## Overarching Goals

Fix UX issues in the Streamlit labelling app's "Unclassified only" mode where images were being permanently lost from the queue on skip/reload, and add a canvas reset button to recover from rendering glitches.

## What Was Accomplished

### 1. Skip and Load New Image No Longer Pop from Queue

Previously, skipping an image or clicking "Load New Image" in unclassified mode would permanently remove the current image from `unclassified_queue.json`. Now, the current image is pushed back to the front of the queue before loading the next one.

- Added `push_unclassified_reading()` to `utils/database.py` — acquires the file lock, reads the queue, inserts the entry at position 0, and writes back.
- Added `_push_back_current_if_unclassified()` helper in the labelling page, called by `load_new_image()`.
- On successful submit, `current_reading` and `current_client` are cleared before calling `load_new_image()`, so the submitted image is not pushed back.

### 2. Reset Annotation Button

Added a "Reset Annotation" button that clears all bounding boxes and resets the canvas without changing the loaded image. This helps when the annotation canvas glitches and shows nothing — the user can reset and start over on the same image.

## Key Files Affected

- `utils/database.py` — Added `push_unclassified_reading()` function
- `pages/1_🏷️_Meter_Labelling.py` — Added `_push_back_current_if_unclassified()`, updated `load_new_image()` to push back before loading, added "Reset Annotation" button, changed action buttons from 2 to 3 columns, clear session state before auto-load after submit

## What Comes Next

- Deploy these changes to the production server
- Continue the discovery/label/retrain cycle to close model coverage gaps
