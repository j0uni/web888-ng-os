# Owner firmware tools

This directory contains source tools, tests and the **public** signing certificate for Jouni's personalized WEB888 firmware. No private keys, configuration backups, generated disk images or bundles are tracked.

Read [the full operator guide](../../docs/owner-firmware.md). Commands in that guide assume this directory as the working directory. Restore your encrypted signing-key backup to `../web888-signing-private/owner.key.pem` when using a fresh clone; do not generate a new identity accidentally. The tracked certificate is the identity already installed on the card. `init-signing.command` intentionally refuses to overwrite it.

Build the Linux tools with `docker --context desktop-linux build -t web888-owner-tools:local .`. Preparation and signing commands use explicit source/output mounts and no network during image handling. Use `fw_image.py prepare --help` and `fw_image.py bundle --help` inside that container for the complete command options.

`update-card.command` is macOS-only and destructive after its target check: it requires a prepared image and verified configuration backups. Read the guide before running it.

Run local tests from the repository root:

```sh
python3 -m unittest discover -s tools/owner-fw -p test_flash.py -v
python3 -m unittest discover -s tools/owner-fw -p test_source_config.py -v
docker --context desktop-linux run --rm --network none -v "$PWD/tools/owner-fw:/kit:ro" web888-owner-tools:local python3 -m unittest discover -s /kit -p test_signatures.py -v
```

The signature tests use disposable encrypted test keys. They never need your real private key or the SD card.
