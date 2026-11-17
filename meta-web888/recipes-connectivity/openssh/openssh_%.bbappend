# SPDX-License-Identifier: GPL-3.0-or-later
# The image takes only openssh-sftp-server from this recipe (recommended
# by packagegroup-core-ssh-dropbear, so that scp from current OpenSSH
# clients, which speaks SFTP, works); the server is dropbear. These are
# flaws in sshd, ssh, sftp or ssh-keygen, none of which is installed
# (ssh and scp are dropbear's).
CVE_STATUS_GROUPS += "CVE_STATUS_WEB888_OPENSSH"
CVE_STATUS_WEB888_OPENSSH = "CVE-2026-106553 CVE-2026-106555 CVE-2026-106583 \
    CVE-2026-106552 CVE-2026-106582 CVE-2026-106584 CVE-2026-106585 CVE-2026-106586 CVE-2026-106587 \
    CVE-2026-106588 CVE-2026-106589"
CVE_STATUS_WEB888_OPENSSH[status] = "not-applicable-config: in sshd, ssh, sftp or ssh-keygen; the image installs only openssh-sftp-server (the SSH server and client are dropbear)"
