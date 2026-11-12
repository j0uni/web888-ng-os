# Independent firmware updates for WEB888

Date: 2026-11-12
Status: Implemented

## Requested outcome
Update the existing v0.2.0 SD card to v0.8.0 and prepare it for independently built, signed network updates, including a future on-device CW skimmer covering 44 kHz. The owner initially selected manual updating, then explicitly authorized the agent to flash and restore the card through Terminal administrator authentication. Preserve existing owner configuration. No CW decoder implementation is requested now.

## Current behavior
The card contains two 512 MiB Linux system slots and a 32 MiB configuration partition. Only its 64 MiB FAT boot partition mounts in macOS. v0.2.0 has no RAUC updater. v0.8.0 adds signed A/B network updates with rollback, but trusts the project's CA. Roots are read-only, with no package manager. Existing configuration selects the standard bitstream. Initially only web888.txt was backed up, and macOS denied raw disk access from Codex. Both configuration sources have since been backed up, restored and verified through the owner-authorized Terminal operation; the updated card was safely ejected at 19:24 Europe/Helsinki on 2026-11-12.

## Proposed behavior
1. Customize the checksum-verified v0.8.0 release image offline, retaining its partition layout and bootloader. Use local Linux container tools to add an owner public signing certificate to the RAUC keyring in BOTH root slots, replacing the upstream CA entirely. Record every modification, tool version and output checksum. Prefer narrowly modifying the released ext4 images over a full Yocto rebuild for this initial preparation.
2. Generate a passphrase-encrypted owner signing key through an interactive local command. Keep it outside Git and firmware artifacts in a private owner-controlled directory; default outputs/web888-signing-private, mode 700 with key mode 600. Ask for the passphrase only in Terminal, never in chat, logs or command arguments. The initial implementation must document a separate secure backup of this directory. Public certificates alone go into firmware. No signing private key goes onto the SD card. Use RAUC/OpenSSL-compatible code-signing certificate constraints and record validity/renewal needs.
3. Deliver a repeatable packaging workflow that embeds the same public certificate into future rootfs images and creates signed verity RAUC bundles compatible with web888. Prefer paths supplied by the owner over embedded credentials. Future CW binaries can be cross-compiled and included in a bundle; they need not compile on the receiver. This is an update mechanism, not a promise that a CW decoder will fit CPU or usable passband limits.
4. Keep signature checking, existing A/B boot selection and mark-good behavior. Reject invalid or untrusted bundles. Keep existing root-slot sizes; no writable add-on system or package manager is introduced. A future oversized image must fail packaging rather than silently changing the card layout.
5. Deliver a manual card-update helper. Identify the card anew from /Volumes/WEB888, show the target, and require confirmation before destructive writes. Back up web888.txt and the entire Linux configuration partition with hashes and restricted permissions before any write. Check old/new configuration partition compatibility; abort on mismatch. Write the prepared image, verify it, restore configuration, verify restoration, and eject. If backup, permissions or verification fail, stop with a precise recovery instruction. macOS administrator authentication happens in Terminal. Do not substitute a raw /dev/disk26 assumption; identifiers can change.
6. Document future manual SSH install/reboot/health-check instructions, but do not connect to a receiver, VPS or remote build server. Remote actions require a separate complete server plan and explicit approval in this conversation.

An unmodified upstream OTA can remove the owner certificate because the keyring is in the root filesystem. The maintained path must personalize upstream rootfs images again before signing/installing. Merely re-signing an unchanged upstream bundle does NOT preserve the keyring. Only the owner certificate is trusted; unmodified upstream bundles must be rejected. Set the manual update helper source to https://jouni.kapsi.fi/web888fw/. Prepare hosting artifacts locally; do not inspect or upload to that server without a separately approved server-side plan.

## Change classification
Security-sensitive change; deployment tooling; firmware migration. The owner subsequently authorized committing and pushing the version to a new branch in j0uni/web888-ng-os. The source recipe, public certificates, tests and CI checks are included; generated images, private keys and configuration backups are excluded. Hosting and receiver services remain outside remote-access approval.

## Docs consulted
- README.md: read-only root, no package manager, local Yocto build scope (about 60 GB and hours); prefer release-image personalization for this task.
- docs/updates.md: v0.2.0 requires a one-time reimage; signed RAUC bundles, configuration preservation, A/B rollback; bootloader excluded from OTA.
- docs/testing-the-sd-image.md: card layout, boot setup and hardware checks.
- docs/release-notes/v0.8.0.md: v0.8.0 contains web888d v0.11.0 and remains a testing prerelease.
- https://rauc.readthedocs.io/en/latest/advanced.html (2026-11-12): trust anchors, passphrase handling and distinction between resigning and replacing rootfs keyrings.
- https://rauc.readthedocs.io/en/latest/reference.html (2026-11-12): system configuration and signed bundle interfaces. Check installed RAUC tool version before relying on specific CLI flags.

## Relevant files and ownership boundaries
- meta-web888/recipes-core/rauc/files/system.conf: current keyring path /usr/lib/rauc/web888-ca.cert.pem and slot configuration; preserve semantics.
- meta-web888/recipes-core/rauc/rauc-conf.bbappend and files/web888-ca.cert.pem: existing trust anchor.
- meta-web888/recipes-core/bundles/web888-bundle.bb: verity bundle format and compatible=web888.
- meta-web888/files/wic/web888-sd.wks: partition layout.
- Local work artifacts and outputs: image preparation, packaging, tests and owner handoff. No upstream code publication.

## Assumptions and open questions
- Approval covers local preparation, the card flash/restore (later explicitly requested), and a new Git branch pushed to the owner firmware fork. Terminal administrator authentication was entered directly by the owner.
- Default signing-key location and encrypted file storage are part of the proposed design; an existing signing identity or hardware token can be used instead if supplied before key creation.
- Docker Desktop is installed locally, aarch64 Linux, with a Unix socket endpoint. No remote container daemon is in scope. Required Linux image utilities and RAUC are not installed natively.
- Future 44 kHz is interpreted as simultaneous RF bandwidth, not a 44 kHz audio sample rate. The standard receiver path is retained. Current channelizer tuner is 12 kS/s; the standard HPSDR path is 48 kS/s, whose usable 44 kHz passband still needs measurement. Decoder selection, CPU budget and acquisition design are deferred.
- Bootloader-dependent future features may require separate boot-file maintenance; this plan covers software/kernel/FPGA changes supported by existing bootloader and image layout, not a guarantee of zero physical intervention forever.

## Task breakdown
| Task | Purpose / areas | Depends on | Verification | Status |
|---|---|---|---|---|
| Approve design | Confirm key custody and signed image workflow | None | Owner approval recorded | Done |
| Establish local tooling and signing identity | Container tooling; encrypted key generation command and public cert | Approval | Cert constraints; private-key exclusion | Done |
| Prepare both root slots | Personalized v0.8.0 image; deterministic modification manifest | Tooling and public cert | e2fsck; compare keyrings; unchanged boot/layout | Done |
| Package future signed updates | Local script and signed sample bundle | Signing identity | Trusted accepted, unrelated/tampered signatures rejected | Done |
| Manual backup/update/restore helper | outputs and Terminal handoff | Prepared image | File-backed disk tests; no real card writes by agent | Done |
| Document owner operation and recovery | Versioned outputs/runbook | All prior tasks | Review commands, sizes, identities and recovery limits | Done |
| Hardware OTA and rollback check | Actual receiver, later approved access or owner execution | Updated card | Boot, retained settings, signed OTA, fallback | Deferred: owner-operated hardware phase |
| CW decoder | Future feature | Separate design and RF/CPU measurements | Actual bandwidth and load tests | Deferred: not this request |

## Testing and verification plan
- Source integrity: SHA-256 of work/web888-ng-sd-v0.8.0.img.xz matches release SHA256SUMS; already passed, value 78cb1480d67d84a4add9e432d93a813e5efa6701e7460cfbf79115f5bec62964. Recheck before modification.
- Image integrity: Linux e2fsck -fn on each modified root image; compare MBR geometry and boot files against the verified original; extract the keyring from both slots and compare public certificates. All required before handoff.
- Signing: openssl verify with code-signing constraints and rauc info --keyring on a sample bundle. Test unrelated signer and tampered payload rejection using actual installed RAUC supported verification flags. Required before handoff; signature-only checks must not be represented as a boot/OTA test.
- Custody: inspect assembled image, bundle contents and output manifest for private key absence. Check local permissions. Required before handoff.
- Migration helper: exercise partition parsing, size mismatch, backup/read/write failure, verification and restore using file-backed test disks. A missing/failed config backup must prevent all writes. Run the meaningful tests supplied with the helper and document exact commands/results. Do not run it against the physical card in automated checks.
- Hardware acceptance (owner): boot latest image, confirm web UI and retained admin login/settings/SSH identity; check RAUC slot status, then signed custom OTA and mark-good/rollback. Not available in this local phase. Do not claim hardware completion without evidence.

## Definition of done
A personalized, verified v0.8.0 image and repeatable owner-signed update packaging workflow are delivered with a manual config-backup/write/restore helper, sample signature tests, checksums, private-key custody instructions and an explicit owner hardware-verification checklist. Both system slots trust the owner certificate. Existing settings and standard bitstream are preserved by the documented migration. No remote operations occur. Planned local verification passes; unavailable hardware tests are explicitly reported. The authorized physical card update completed with a success record and progress log: full firmware read-back matched the prepared image, both configuration sources matched their verified backups, and the card was ejected. Hardware boot/OTA/rollback testing is a separate deferred acceptance phase.

## Implementation prompt
Use $project-implementation-lead with this document as the implementation brief. Implement the approved local image customization, key-generation instructions, signed-bundle packaging, fail-closed migration helper, tests and owner runbook. Work within the local workspace and outputs; do not operate on remote servers or generate an unencrypted signing key. The owner later authorized the physical card flash/restore and a new Git branch push; those explicit instructions supersede the earlier manual-only/local-only scope. Preserve boot layout, rollback, configuration and signature enforcement. If tool support, trust design, key custody or verification assumptions materially fail, update this document to Proposed and return for review rather than silently changing the approach. Record exact tool versions, tests, file paths, modifications and all unrun hardware checks.

## Implementation notes
- Added `tools/owner-fw/` for offline image personalization, encrypted-key creation, verity bundle signing, macOS flash/config restore/recovery, and meaningful regression tests. Generated artifacts and private directories are ignored and not staged.
- Replaced both Yocto public certificate files with the owner's public certificate. Added `web888-owner-update` recipe and included it in the image; runtime helper and source record exactly match the personalized image.
- Added CI checks for migration logic, source/runtime consistency, and real RAUC signature/payload verification. Image building and release publication depend on these checks.
- The packager validates effective RAUC config precedence, the owner keyring path and code-signing policy, hardware/slot identity, and the retained updater/source. A misleading /etc override is rejected.
- Kept host tooling compatible with macOS Python 3.9 by using a streaming hash rather than hashlib.file_digest.
- Added `docs/owner-firmware.md`, tool README, and updated update/signing docs. Independent firmware updates use https://jouni.kapsi.fi/web888fw/ . No hosting inspection or upload was attempted.
- First physical attempt hit macOS auto-remount between phases. Corrected the helper to hold a single writable raw descriptor across writing, read-back, config restoration and verification; recovery reused the original verified backup. Second attempt completed, restored both configuration sources and ejected the card.
- The source-publishing request is fulfilled by a new branch, preserving the upstream v0.8.0 base. Source changes do not modify the server application repository.

## Verification results
- Published original firmware checksum matched before personalization.
- Both modified slot filesystems passed `e2fsck -fn`; each inserted file was extracted and compared. All bytes outside root slots matched the original image. Public owner certificate fingerprint: `94:89:74:CA:03:5B:66:F1:53:34:4C:71:15:50:85:1D:1A:48:BC:5D:1D:8B:25:69:85:DE:0B:79:9A:E3:6E:AF`.
- `python3 -m unittest discover -s tools/owner-fw -p test_flash.py -v`: 13 passed. Includes partial/zero writes, invalid or missing backups, corrupt boot settings backup, short reads, image size mismatch, write errors and full config restoration.
- `python3 -m unittest discover -s tools/owner-fw -p test_source_config.py -v`: 3 passed. Confirms all public certificate copies match, runtime updater/source match the source recipe, and license checksum follows the existing project recipe.
- Linux RAUC signature integration test passed, including trusted verification, unrelated signer rejection, signature tampering rejection, full payload extraction and verity corruption rejection. The actual bundle packager also created and verified a disposable ext4 update and refused a root image with a mismatching owner identity.
- Workflow YAML parsed with the installed Ruby YAML parser and the publication dependency gate was checked; `git diff --check` passed.
- Host RAUC 1.13 must load an explicit configuration to enforce `check-purpose=codesign`; an attempted override without a host config did not apply the intended policy. Tooling now explicitly loads the matching host policy.
- Real card: firmware read-back and both configuration restores verified, then safe ejection, observed through the success record and log on 2026-11-12 at 19:24 Europe/Helsinki.
- A full Yocto rebuild was not run. Recipe/build parsing and actual rebuilt-image validation remain unverified; the running-card deliverable was personalized directly from the verified release image. Unattended encrypted-key signing in BitBake/CI is not configured; interactive local signing is the verified path.
- Receiver boot, RF behavior, real OTA, mark-good and rollback were not tested: the card is ejected and no remote receiver access is approved. Kapsi hosting/range support was not inspected or changed.

## Remaining risks
Keep a separate secure backup of the encrypted signing key and original card configuration. Recovery restores new firmware plus original configuration, not every byte of the old card. Losing the only signing key can require physical recovery. Do not install an unmodified upstream rootfs: it removes owner trust, and upstream-signed bundles are intentionally rejected. v0.8.0 is a testing prerelease. Real-board boot, usable 44 kHz passband, CW CPU capacity and hardware rollback remain to be verified. HTTP range support and initial bundle publication were subsequently verified under the separately approved hosting plan (below). The full source-built Yocto image has not been rebuilt in this task.

## Subsequent hosting deployment — 2026-11-12
The owner supplied the Kapsi SSH account and hosting directory and explicitly approved a complete scoped server-side publishing plan. The initial signed v0.8.0-owner1 bundle is published at https://jouni.kapsi.fi/web888fw/ . Only public bundle/metadata/certificate files were uploaded. Server-side SHA-256, public HTTPS metadata, HTTP 206 range requests and a complete public-download checksum comparison verified. No receiver was updated or restarted during publication. Source/private-key separation and the original hardware-testing limits still apply.
