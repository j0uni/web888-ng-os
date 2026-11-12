#!/bin/bash
set -euo pipefail
KIT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
KEY_DIR="$KIT_DIR/../web888-signing-private"
VERSION=${1:-v0.8.0-owner1}
case "$VERSION" in *[!A-Za-z0-9._+-]*|'') echo 'Invalid version' >&2; exit 2 ;; esac
if [ ! -t 0 ]; then echo 'Run this interactively in Terminal for the encrypted signing-key passphrase.' >&2; exit 2; fi
mkdir -p "$KIT_DIR/publish"
BUNDLE="$KIT_DIR/publish/web888-$VERSION.raucb"
if [ -e "$BUNDLE" ]; then echo 'Version already exists. Choose a new version.' >&2; exit 2; fi
printf '%s\n' 'The next prompt is your firmware signing-key passphrase, not the Mac administrator password.'
docker --context desktop-linux run --rm -it --network none \
  -v "$KIT_DIR:/kit" -v "$KEY_DIR:/keys:ro" web888-owner-tools:local \
  python3 /kit/fw_image.py bundle --rootfs /kit/prepared/rootfs.ext4 \
  --cert /kit/owner.cert.pem --key /keys/owner.key.pem \
  --version "$VERSION" --output "/kit/publish/web888-$VERSION.raucb"
# latest is a local complete copy. Publish it only after uploading the versioned file.
cp "$BUNDLE" "$KIT_DIR/publish/.latest.raucb.tmp"
mv "$KIT_DIR/publish/.latest.raucb.tmp" "$KIT_DIR/publish/latest.raucb"
python3 "$KIT_DIR/release_manifest.py" "$KIT_DIR" "$VERSION"
printf '\nSigned hosting files are ready in %s/publish\nNothing has been uploaded.\n' "$KIT_DIR"
