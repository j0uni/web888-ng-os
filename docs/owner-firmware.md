# WEB888 owner firmware

This guide applies to the owner-firmware branch. All relative command/tool paths below refer to `tools/owner-fw/`. Generated artifacts and private backups exist only in the local working environment; they are not in Git. On a fresh clone, restore your encrypted private-key backup alongside that tool directory; the public certificate is already tracked.

Prepared 2026-11-12 from web888-ng-os v0.8.0 (web888d v0.11.0).
Update download source: https://jouni.kapsi.fi/web888fw/

This firmware trusts only your certificate. The project's original signing CA is replaced in both system slots. Existing A/B boot, watchdog, mark-good and rollback behavior is retained. The update helper initiates an update only when you run it; it does not poll or automatically install/reboot.

## Your signing identity

Public certificate SHA-256 fingerprint:

`94:89:74:CA:03:5B:66:F1:53:34:4C:71:15:50:85:1D:1A:48:BC:5D:1D:8B:25:69:85:DE:0B:79:9A:E3:6E:AF`

The encrypted private key is in `../web888-signing-private/owner.key.pem`. It expires with the current certificate on 2036-11-09; plan key/certificate rotation before then. Keep a separate secure backup of that private directory and its passphrase. Do not upload it, configuration backups, or this entire outputs folder. Never put the private key on the receiver. Losing the only trusted signing key can require physical SD-card recovery.

## Completed card operation

The owner-authorized physical card operation completed on 2026-11-12 at 19:24 Europe/Helsinki: firmware read-back and both configuration restores verified, then the card was ejected. The first attempt hit a macOS FAT auto-remount; recovery reused the verified original backup. The updater now holds one writable raw-device descriptor throughout write/read-back/config restore. Receiver boot has not been tested.

## Repeating the card operation

`update-card.command` launches the macOS migration with sudo. It identifies the card from `/Volumes/WEB888`, confirms removable physical media, verifies the personalized image, backs up and hashes `web888.txt` and the entire Linux configuration partition, writes and reads back the image, restores both configuration sources, verifies them and ejects. By default it asks you to type the inspected target identifier; the agent may supply `--confirm-device diskN` after inspecting that exact card and receiving your authorization.

Success is recorded in `flash-result.json`. `flash.log` records progress. Configuration backups are private sibling directories `../web888-config-backup-YYYYMMDD-HHMMSS/`. A previous backup of web888.txt alone is NOT a substitute for the full config.ext4 backup, which includes password hashes, daemon settings and SSH host keys.

Do not remove the card or power down the computer while writing/verifying. If anything fails after writing begins, do not boot the card. Use the verified original backup for recovery; never replace it with a backup of a half-written card.

## Recovery after a failed write or restoration

1. Keep the original `web888-config-backup-...` directory intact.
2. Reinsert the card if necessary. In Terminal, run `diskutil list` and identify the SD card by its physical reader and capacity. The identifier may have changed; do not assume disk26.
3. From this directory, run:

```sh
sudo python3 flash_card.py --restore-backup /absolute/path/to/original/web888-config-backup-YYYYMMDD-HHMMSS --device /dev/diskN
```

Replace both placeholders. This mode works even if the FAT volume cannot mount. It reuses and verifies the original backup, rewrites the prepared firmware, restores both configuration sources, verifies and ejects. It still checks physical removable media, capacity and the explicit target confirmation.

This is configuration-only recovery, as requested. It restores the new firmware plus your original configuration; it does not reproduce every byte of the old card.

## Sign a network update locally

Run `sign-bundle.command` in Terminal, optionally followed by a new unique version such as `v0.8.0-owner2`. Enter the firmware key passphrase at the OpenSSL/RAUC prompt. This is separate from your Mac administrator password.

The command uses the local Docker Desktop engine, with networking disabled, and mounts the encrypted key directory read-only. It checks rootfs size, filesystem integrity and that your certificate remains embedded before building a verity RAUC bundle. Host verification explicitly uses the same `check-purpose=codesign` policy as the device. A no-config host RAUC command defaults to a different certificate purpose and must not be used to judge this key.

Completed signed bundles and `latest.raucb` go into `publish/`, alongside `SHA256SUMS` and informational `latest.json`. A failed signing operation does not update `latest.raucb`. Never reuse a published version filename with different contents.

## Hosting and installing future updates

No hosting server has been inspected or changed. To publish later, upload only public contents of `publish/` into the approved web directory serving https://jouni.kapsi.fi/web888fw/ . Upload the versioned bundle first and replace `latest.raucb` only after the complete upload is verified, preferably with a same-filesystem atomic rename. The host must support HTTP byte-range requests for RAUC streaming; this still needs verification under a separately approved server-access plan. Signatures are authoritative; SHA256SUMS and latest.json are informational integrity/version aids.

After a signed bundle is actually hosted, the receiver's manual command is:

```sh
web888-owner-update
```

It installs `https://jouni.kapsi.fi/web888fw/latest.raucb` into the inactive slot. A specific version can be supplied as a `.raucb` filename. After a successful installation, reboot manually, then check `rauc status`, `systemctl status web888d` and the web UI. Allow at least a minute for the slot to be marked good. Confirm the signing certificate and updater are retained after boot. No receiver/hosting SSH connection or reboot has been performed by this preparation.

A future CW skimmer should be built for the device, included in a personalized rootfs and delivered through this same signed bundle path. Current receiver bandwidth, usable filter passband and decoder CPU load still need validation; nothing here implements CW decoding.

## Repeatable image preparation

The local container image `web888-owner-tools:local` contains Python, e2fsprogs, RAUC 1.13, squashfs-tools and OpenSSL. `Dockerfile` records the pinned Debian base. Rebuild with `docker --context desktop-linux build -t web888-owner-tools:local .` if needed. The initial source image was verified against its published SHA256SUMS before modification.

`fw_image.py prepare --source SOURCE.img.xz --sha256 VERIFIED_HASH --base-version v0.8.0 --cert owner.cert.pem --output NEW_DIRECTORY` personalizes both slots of a compatible image and exports `rootfs.ext4` for OTA packaging. Run it in the Linux container with explicit read-only source mounts and no private-key mount. The output directory must not exist. It preserves all non-rootfs bytes and checks both modified filesystems. Metadata records source, artifact hashes, partitions and tool versions.

For future modified rootfs images, use `fw_image.py bundle --rootfs ROOTFS.ext4 --cert owner.cert.pem --key ENCRYPTED_KEY --output NEW.raucb --version UNIQUE_VERSION` in the same interactive container. The rootfs must already include your certificate at `/usr/lib/rauc/web888-ca.cert.pem`. Packaging refuses a rootfs without the matching certificate or larger than a 512 MiB slot. A replacement built from upstream sources must keep the owner's trust and updater; simply re-signing an unmodified upstream bundle would not do that.

## Verification

- Original compressed image: SHA-256 `78cb1480d67d84a4add9e432d93a813e5efa6701e7460cfbf79115f5bec62964`.
- Both personalized root filesystems passed `e2fsck -fn`; inserted files were extracted and compared exactly. No private key was mounted during personalization.
- Both slot keyrings contain exactly the public owner certificate. All image bytes outside the root slots were checked unchanged.
- `python3 -m unittest discover -s . -p test_flash.py -v`: 13 file-backed migration checks, including corrupted/missing backups, short reads/writes, failed writes and incompatible partition size.
- Linux container: `python3 -m unittest discover -s /kit -p test_signatures.py -v`: real RAUC accepts a trusted signed bundle, rejects an unrelated signer and corrupted signature, verifies extraction, and rejects a damaged verity payload. Uses disposable encrypted test keys, not your private key.
- Initial real-board boot, retained admin login, RF behavior, an actual OTA, mark-good and fallback still require hardware verification after the card is returned to the receiver. Do not treat local tests or successful flashing as evidence of a completed hardware boot/rollback test.

Sources: https://github.com/jeskko/web888-ng-os/releases/tag/v0.8.0 ; https://github.com/jeskko/web888-ng-os/blob/main/docs/updates.md ; https://rauc.readthedocs.io/en/latest/advanced.html
