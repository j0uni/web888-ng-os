#!/bin/bash
set -euo pipefail
KIT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
cd "$KIT_DIR"
PYTHON_BIN=$(command -v python3)
"$PYTHON_BIN" -c 'import lzma, plistlib'
printf '%s\n' 'Administrator authentication is required for SD-card access.' 'The updater verifies configuration backups before any writes.'
sudo "$PYTHON_BIN" "$KIT_DIR/flash_card.py" "$@" 2>&1 | tee "$KIT_DIR/flash.log"
