#!/bin/bash
# One-time setup: a Python 3.13 venv with Blender-as-a-module (bpy) plus image/video helpers.
# Also needs ffmpeg/ffprobe on PATH (apt install ffmpeg, or brew install ffmpeg).
set -euo pipefail
cd "$(dirname "$0")"
PKGS="bpy==5.2.2 numpy pillow scipy opencv-python-headless"   # bpy 5.2 wheels target Python 3.13
if command -v uv >/dev/null; then
  uv venv -q -p 3.13 bvenv
  VIRTUAL_ENV=$PWD/bvenv uv pip install -q $PKGS
else
  python3.13 -m venv bvenv
  bvenv/bin/pip install -q $PKGS
fi
bvenv/bin/python -c "import bpy, cv2, scipy; print('bpy', bpy.app.version_string, '| ok')"
command -v ffmpeg >/dev/null || echo "WARNING: ffmpeg not found on PATH"
