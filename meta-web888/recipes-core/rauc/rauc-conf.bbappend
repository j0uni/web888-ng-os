# SPDX-License-Identifier: GPL-3.0-or-later
# This fork trusts only the owner's self-signed code-signing certificate.
# The upstream project's CA is intentionally replaced.
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
RAUC_KEYRING_FILE = "web888-ca.cert.pem"
