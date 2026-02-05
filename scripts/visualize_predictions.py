"""
Visualize YOLO OBB predictions on validation images.

Runs inference on val set and saves images with predicted bounding boxes.

Usage:
    uv run python scripts/visualize_predictions.py                    # Use best.pt
    uv run python scripts/visualize_predictions.py --model last.pt    # Use specific checkpoint
    uv run python scripts/visualize_predictions.py --num 20           # Limit to 20 images
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
RUNS_DIR = PROJECT_ROOT / "runs"
WEIGHTS_DIR = RUNS_DIR / "meter_obb" / "weights"
OUTPUT_DIR = RUNS_DIR / "meter_obb" / "predictions"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default="best.pt",
        help="Model checkpoint to use (default: best.pt)",
    )
    parser.add_argument(
        "--num",
        type=int,
        default=0,
        help="Number of images to process (0 = all)",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Confidence threshold (default: 0.25)",
    )
    args = parser.parse_args()

    model_path = WEIGHTS_DIR / args.model
    if not model_path.exists():
        log.error(f"Model not found: {model_path}")
        return

    val_images_dir = DATASET_DIR / "images" / "val"
    if not val_images_dir.exists():
        log.error(f"Validation images not found: {val_images_dir}")
        return

    image_paths = sorted(val_images_dir.glob("*.jpg"))
    if args.num > 0:
        image_paths = image_paths[: args.num]

    log.info(f"Loading model from {model_path}")
    model = YOLO(str(model_path))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info(f"Running inference on {len(image_paths)} images...")
    results = model.predict(
        source=[str(p) for p in image_paths],
        conf=args.conf,
        save=True,
        project=str(OUTPUT_DIR),
        name="val",
        exist_ok=True,
    )

    log.info(f"Predictions saved to: {OUTPUT_DIR / 'val'}")

    water_count = 0
    electricity_count = 0
    for r in results:
        if r.obb is not None and r.obb.cls is not None:
            for cls_id in r.obb.cls:
                if int(cls_id) == 0:
                    water_count += 1
                elif int(cls_id) == 1:
                    electricity_count += 1

    log.info(f"Detections: {water_count} water, {electricity_count} electricity")


if __name__ == "__main__":
    main()
