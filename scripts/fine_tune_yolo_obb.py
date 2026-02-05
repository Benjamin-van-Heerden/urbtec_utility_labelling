"""
Fine-tune YOLO26n-OBB on meter detection dataset.

Run prepare_dataset.py first to create the dataset.

Usage:
    uv run python scripts/fine_tune_yolo_obb.py          # Start fresh
    uv run python scripts/fine_tune_yolo_obb.py --resume # Resume from last checkpoint
"""

import argparse
import logging
from pathlib import Path

from ultralytics import YOLO

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATASET_DIR = PROJECT_ROOT / "datasets" / "meter_obb"
DATA_YAML = DATASET_DIR / "data.yaml"
RUNS_DIR = PROJECT_ROOT / "runs"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resume", action="store_true", help="Resume from last checkpoint"
    )
    args = parser.parse_args()

    if not DATA_YAML.exists():
        log.error(f"Dataset not found at {DATA_YAML}")
        log.error("Run prepare_dataset.py first")
        return

    last_pt = RUNS_DIR / "meter_obb" / "weights" / "last.pt"

    if args.resume:
        if not last_pt.exists():
            log.error(f"No checkpoint found at {last_pt}")
            return
        log.info(f"Resuming from {last_pt}")
        model = YOLO(str(last_pt))
    else:
        log.info("Loading YOLO26n-OBB pretrained model...")
        model = YOLO("yolo26n-obb.pt")

    log.info("Starting training...")
    model.train(
        data=str(DATA_YAML),
        epochs=100,
        imgsz=1024,
        batch=-1,  # auto batch size
        device="mps",  # Apple Silicon GPU
        project=str(RUNS_DIR),
        name="meter_obb",
        patience=20,  # early stopping
        save=True,
        save_period=5,  # checkpoint every 5 epochs
        plots=True,
        verbose=True,
        exist_ok=True,  # allow resuming into same directory
        resume=args.resume,
    )

    log.info("Training complete!")
    log.info(f"Results saved to: {RUNS_DIR / 'meter_obb'}")
    log.info(f"Best model: {RUNS_DIR / 'meter_obb' / 'weights' / 'best.pt'}")


if __name__ == "__main__":
    main()
