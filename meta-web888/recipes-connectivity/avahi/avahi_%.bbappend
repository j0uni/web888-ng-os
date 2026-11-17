# SPDX-License-Identifier: GPL-3.0-or-later
# avahi-daemon answers <hostname>.local. Its simple-protocol socket
# (/run/avahi-daemon/socket) is local only, and root is the only account
# with a login.
CVE_STATUS[CVE-2025-59529] = "not-reachable: a local denial of service through avahi-daemon's local socket; root is the only account with a login"
