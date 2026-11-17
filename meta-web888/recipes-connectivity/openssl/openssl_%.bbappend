# SPDX-License-Identifier: GPL-3.0-or-later
# OpenSSL 3.5.9 flaws without a fixed 3.5 release yet (2026-11-17; drop
# these when oe-core's wrynose has one). In the image libcrypto/libssl
# are used by rauc (bundle signatures: CMS verify, and decrypting), kmod
# (module signatures), libcurl (rauc's HTTPS; built without HTTP/3, so no
# QUIC) and the openssl tool (root only). web888d has its own TLS
# (rustls/ring) and dropbear its own crypto.
CVE_STATUS_GROUPS += "CVE_STATUS_WEB888_OPENSSL_GCMSIV CVE_STATUS_WEB888_OPENSSL_QUIC CVE_STATUS_WEB888_OPENSSL_CMS"
CVE_STATUS_WEB888_OPENSSL_GCMSIV = "CVE-2026-88823 CVE-2026-95692"
CVE_STATUS_WEB888_OPENSSL_GCMSIV[status] = "ignored: AES-GCM-SIV, which nothing in the image uses (only the root-only openssl tool could be told to)"
CVE_STATUS_WEB888_OPENSSL_QUIC = "CVE-2026-95691"
CVE_STATUS_WEB888_OPENSSL_QUIC[status] = "ignored: the OpenSSL QUIC client, which nothing in the image uses (curl is built without HTTP/3: no ngtcp2/nghttp3, no openssl-quic)"
CVE_STATUS_WEB888_OPENSSL_CMS = "CVE-2026-107496"
CVE_STATUS_WEB888_OPENSSL_CMS[status] = "ignored: CMS_encrypt with an attacker's recipient certificate; on the device rauc only verifies and decrypts bundles (rauc encrypt runs on the build host with the operator's certificates), and the openssl tool is root only"
