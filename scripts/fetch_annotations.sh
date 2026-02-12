#!/usr/bin/env bash
set -euo pipefail

REMOTE_USER="ubuntu"
REMOTE_HOST="34.242.238.192"
REMOTE_PATH="/home/ubuntu/projects/urbtec_utility_labelling/annotations.db"
SSH_KEY="$HOME/.ssh/urbion-ai-server-key-pair.pem"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOCAL_PATH="$PROJECT_ROOT/annotations.db"

echo "Fetching annotations.db from $REMOTE_HOST..."
scp -i "$SSH_KEY" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH" "$LOCAL_PATH"
echo "Done. Saved to $LOCAL_PATH"
