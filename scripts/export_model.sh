#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MODEL_PATH="$PROJECT_ROOT/runs/meter_obb/weights/best.pt"
DEST_DIR="/Users/benjamin/Documents/Urbtec/Urbion-AI/yolo_obb"

if [ ! -f "$MODEL_PATH" ]; then
    echo "Error: $MODEL_PATH not found"
    exit 1
fi

cp "$MODEL_PATH" "$DEST_DIR/best.pt"
echo "Copied best.pt to $DEST_DIR/best.pt"
