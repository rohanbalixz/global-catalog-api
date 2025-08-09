#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build/stream_processor"

mkdir -p "$BUILD_DIR"
# Place handler at the zip root (Lambda handler = "handler.handler")
cp "$ROOT_DIR/src/stream_processor/handler.py" "$BUILD_DIR/handler.py"

cd "$BUILD_DIR"
zip -r ../stream_processor.zip handler.py >/dev/null

echo "Built: $ROOT_DIR/build/stream_processor.zip"
