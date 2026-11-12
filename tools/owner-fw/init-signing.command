#!/bin/bash
set -euo pipefail
umask 077
KIT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
KEY_DIR="$KIT_DIR/../web888-signing-private"
mkdir -p "$KEY_DIR"
chmod 700 "$KEY_DIR"
if [ -e "$KEY_DIR/owner.key.pem" ] || [ -e "$KIT_DIR/owner.cert.pem" ]; then
  echo 'Signing files already exist. Refusing to replace your identity.' >&2
  exit 1
fi
KEY_TMP=$(mktemp -d "$KEY_DIR/.init.XXXXXX")
trap 'rm -rf "$KEY_TMP"' EXIT
printf '%s\n' 'Choose a strong passphrase for your firmware signing key.' 'Enter it only at the OpenSSL prompts below. Keep a separate secure backup of the key and its passphrase.'
openssl req -new -x509 -newkey rsa:3072 -sha256 -days 3650 \
  -subj '/CN=Jouni WEB888 Firmware Owner/' \
  -addext 'basicConstraints=critical,CA:TRUE' \
  -addext 'keyUsage=critical,digitalSignature,keyCertSign,cRLSign' \
  -addext 'extendedKeyUsage=codeSigning' \
  -keyout "$KEY_TMP/owner.key.pem" -out "$KEY_TMP/owner.cert.pem"
grep -q 'BEGIN ENCRYPTED PRIVATE KEY' "$KEY_TMP/owner.key.pem"
chmod 600 "$KEY_TMP/owner.key.pem"
mv "$KEY_TMP/owner.key.pem" "$KEY_DIR/owner.key.pem"
cp "$KEY_TMP/owner.cert.pem" "$KEY_DIR/owner.cert.pem"
cp "$KEY_TMP/owner.cert.pem" "$KIT_DIR/owner.cert.pem"
printf '\nPublic signing identity:\n'
openssl x509 -in "$KIT_DIR/owner.cert.pem" -noout -fingerprint -sha256 -dates
printf '\nCreated encrypted private key in %s\nPublic certificate ready in %s\n' "$KEY_DIR" "$KIT_DIR/owner.cert.pem"
