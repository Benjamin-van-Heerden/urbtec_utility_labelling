---
created_at: '2026-02-12T15:27:15.440208'
username: benjamin_van_heerden
---
# Work Log - Scripts and Dataset Stability Improvements

## Overarching Goals

Create helper scripts for the training workflow (fetching annotations, exporting models) and fix a dataset stability issue where adding new annotations would corrupt train/val splits.

## What Was Accomplished

### 1. SCP Script for Fetching Annotations

Created `scripts/fetch_annotations.sh` to pull the latest `annotations.db` from the production server (`ubuntu@34.242.238.192`) via SCP, overwriting the local copy.

### 2. Model Export Script

Created `scripts/export_model.sh` to copy `runs/meter_obb/weights/best.pt` to `/Users/benjamin/Documents/Urbtec/Urbion-AI/yolo_obb/best.pt` for use in the Urbion-AI repo. The model is small enough (17M) to version control via git.

### 3. Deterministic Train/Val Splits

Fixed a bug in `scripts/prepare_dataset.py` where `assign_splits` used `random.seed(42)` + shuffle. Adding new annotations would change the shuffle order for all existing annotations, causing images to be in one split folder but labels written to the other.

Replaced with hash-based splitting: each annotation's ID is hashed with MD5 to deterministically assign it to train (80%) or val (20%). New annotations never affect existing split assignments, so the resumable download works correctly.

This requires a one-time `rm -rf datasets/meter_obb` before re-running to clear the old split state.

### 4. Reduced Rate Limit Retries

Reduced `MAX_RETRIES` from 5 to 2 in `prepare_dataset.py`. The exponential backoff with 5 retries caused the script to stall for over a minute on persistently rate-limited URLs. With 2 retries the script moves on quickly, and failed images get picked up on the next resumable run.

### 5. YOLO OBB Detection Framework

Provided a `detect.py` module for use in the Urbion-AI repo. Key design:
- `detect_meter(image_path)` returns a single `MeterDetection` or `None`
- When multiple bounding boxes are detected, selects the one closest to image center
- Returns class_id, class_name, confidence, and OBB corner points

## Key Files Affected

- `scripts/fetch_annotations.sh` — New script to SCP annotations.db from production
- `scripts/export_model.sh` — New script to copy best.pt to Urbion-AI repo
- `scripts/prepare_dataset.py` — Replaced random shuffle splits with hash-based splits; reduced MAX_RETRIES from 5 to 2; replaced `random` import with `hashlib`

## What Comes Next

- One-time `rm -rf datasets/meter_obb` then re-run `prepare_dataset.py` to rebuild with stable splits
- Full retraining run (100 epochs or early stopping) with the updated dataset
- Integrate `detect.py` into the Urbion-AI codebase
- Continue collecting annotations to grow the training set
