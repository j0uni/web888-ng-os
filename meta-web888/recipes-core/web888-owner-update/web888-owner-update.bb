# SPDX-License-Identifier: GPL-3.0-or-later
SUMMARY = "Manual owner-signed firmware updates from Jouni's update source"
LICENSE = "GPL-3.0-or-later"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/GPL-3.0-or-later;md5=1c76c4cc354acaac30ed4d5eefea7245"

SRC_URI = "file://web888-owner-update file://web888-owner-source"
S = "${UNPACKDIR}"
RDEPENDS:${PN} = "rauc"

do_install() {
	install -D -m 0755 ${S}/web888-owner-update ${D}${bindir}/web888-owner-update
	install -D -m 0644 ${S}/web888-owner-source ${D}${sysconfdir}/web888-owner-source
}
