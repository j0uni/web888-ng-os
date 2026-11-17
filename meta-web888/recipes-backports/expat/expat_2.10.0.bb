# SPDX-License-Identifier: MIT
# Backported from OpenEmbedded-Core master (34991d0, 2026-11-09) for CVE
# fixes that wrynose doesn't have yet (licence lines in wrynose's "&"
# syntax). Drop it when wrynose catches up.

SUMMARY = "A stream-oriented XML parser library"
DESCRIPTION = "Expat is an XML parser library written in C. It is a stream-oriented parser in which an application registers handlers for things the parser might find in the XML document (like start tags)"
HOMEPAGE = "https://github.com/libexpat/libexpat"
SECTION = "libs"
LICENSE = "MIT"

LIC_FILES_CHKSUM = "file://COPYING;md5=f4fedd6116da0e171f7cb4d2923d7ac2"

VERSION_TAG = "${@d.getVar('PV').replace('.', '_')}"

SRC_URI = "${GITHUB_BASE_URI}/download/R_${VERSION_TAG}/expat-${PV}.tar.xz  \
           file://run-ptest \
           "

GITHUB_BASE_URI = "https://github.com/libexpat/libexpat/releases/"
UPSTREAM_CHECK_REGEX = "releases/tag/R_(?P<pver>.+)"

SRC_URI[sha256sum] = "c624ba2998fc65df1163a49641ff3f9ab73138b11641d92c86bee0fb01b1bc7f"

EXTRA_OECMAKE:class-native += "-DEXPAT_BUILD_DOCS=OFF"

RDEPENDS:${PN}-ptest += "bash"

inherit cmake lib_package ptest github-releases

do_install_ptest:class-target() {
	install -m 755 ${B}/tests/runtests* ${D}${PTEST_PATH}
	install -m 755 ${B}/tests/benchmark/benchmark ${D}${PTEST_PATH}
}

BBCLASSEXTEND += "native nativesdk"

CVE_PRODUCT = "expat libexpat"

# Not fixed in 2.10.0 yet (2026-11-17). The image's users of libexpat are
# dbus and avahi-daemon; xmlwf (expat-bin) is not installed.
CVE_STATUS[CVE-2026-128241] = "not-applicable-config: in xmlwf, which the image doesn't install"
CVE_STATUS[CVE-2026-124317] = "not-applicable-config: only with an application's unknown-encoding handler; no program in the image registers one (XML_SetUnknownEncodingHandler)"
