#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${1:-.}"

if [[ ! -d "$TARGET_DIR/.git" ]]; then
  echo "Target must be an existing Git checkout: $TARGET_DIR" >&2
  exit 1
fi

TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

if [[ "$SOURCE_DIR" == "$TARGET_DIR" ]]; then
  echo "Source and target are the same checkout; nothing to install." >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required to copy the bootstrap safely." >&2
  exit 1
fi

rsync -a --ignore-existing \
  --exclude=.git/ \
  --exclude=.venv/ \
  --exclude=.pytest_cache/ \
  --exclude=.ruff_cache/ \
  --exclude=.DS_Store \
  "$SOURCE_DIR"/ "$TARGET_DIR"/

echo "Bootstrap copied into $TARGET_DIR without overwriting existing files."
echo "Review skipped/conflicting files, then commit the intended foundation."
