# Updates over the network (RAUC)

From v0.3.0 on, a unit running the SD card image can update itself
without taking the card out. Each release has an update bundle,
`web888-ng-<version>.raucb`, next to the card images. The bundle holds
the whole system: kernel, device tree, bitstreams, web888d and the rest.
Every bitstream is in the system, and `bitstream =` in `web888.txt`
chooses one, so an update keeps the unit's choice (v0.2.0 and v0.3.0's
`-channelizer` image only had that line set). A unit without the line
gets the release's default: the standard bitstream up to v0.6.0, the
channelizer from v0.7.0 (`bitstream = standard` keeps the standard
one).

Units on v0.1.0 or v0.2.0 have no RAUC: write the v0.3.0 card image
once, and update over the network from then on.

## Owner firmware branch

This branch trusts only the owner certificate and installs updates from
https://jouni.kapsi.fi/web888fw/ . See [owner-firmware.md](owner-firmware.md)
for local signing, publication requirements, migration and recovery.
The original project's bundles are not trusted directly.

## Updating

Over SSH (an `ssh_key` in `web888.txt`):

```sh
web888-owner-update
reboot
```

* **Streamed:** RAUC reads the bundle straight from the URL, checking it
  as it goes, and writes it to the root slot not running now. Nothing is
  downloaded to the unit first. The receiver keeps running during the
  install.
* **Checked before it boots:** the bundle must be signed by the
  project's update key, and made for this hardware (`compatible=web888`).
  RAUC refuses anything else.
* **The new slot boots first,** with three tries. If web888d runs for a
  minute, the slot is marked good (`web888-boot-ok`). If the new system
  doesn't come up, the unit goes back to the old slot after three boots.
  The watchdog resets a hang.
* **Settings stay:** `web888.txt`, the admin password, the configuration
  partition and the SSH host keys are untouched by an update.

`rauc status` shows both slots, which one booted and which boots next.
A power cut during an install leaves the old slot as it was. The unit
boots it, and the install can simply be run again.

## What an update doesn't change

* `BOOT.BIN` and `u-boot.img` on the card's FAT partition. They aren't
  A/B, so a mistake there could leave the unit unbootable, and an update
  leaves them alone. A release that needs new ones will say so, and they
  are then copied to the card by hand.
* The U-Boot environment (the boot chooser's state) carries over.

## Signing

This branch uses the owner's self-signed code-signing certificate as the
only trust anchor (`/usr/lib/rauc/web888-ca.cert.pem`); the same public
certificate is supplied by the bundle recipe. The private key is provided
externally, never committed or placed on the card. The device enforces
`check-purpose = codesign` and retains the existing signing-time handling.

For encrypted-key local signing, use `tools/owner-fw/sign-bundle.command`.
The helper explicitly configures the host's code-signing verification policy,
checks that the rootfs retains the owner's certificate, and produces a signed
verity bundle. Keep that trust anchor in every future rootfs. A simple re-sign
of an upstream rootfs would remove it on the next boot.

A full Yocto image/bundle rebuild was not run during this local personalization.
Encrypted-key passphrase handling for unattended BitBake/CI signing has not been
configured; do not assume an encrypted key file alone is sufficient for that
pipeline. Local interactive signing is the verified path.

## Tested

In the emulator (web888-ng-hw `emu/tests/ota.sh`, with the SD card image
booted through the boot ROM as on the board):

* streaming install into slot B, then a boot into B, marked good;
* a power cut in the middle of an install;
* a bad update that doesn't boot, with the unit going back to the old
  slot.
