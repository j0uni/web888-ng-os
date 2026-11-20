# SPDX-License-Identifier: MIT
# Adapted from meta-openembedded's meta-networking chrony_4.8.bb (wrynose,
# 37f675a8bc, MIT), without meta-oe's dependencies: no PPS (pps-tools), no
# editline in chronyc, no SysV init script, no seccomp filter. The image
# has no meta-oe; drop this recipe if meta-networking is ever added.

SUMMARY = "Versatile implementation of the Network Time Protocol"
DESCRIPTION = "chronyd keeps the system clock in time from NTP servers and \
reference clocks; chronyc monitors and controls it. On the Web-888 it also \
takes the time-code stations web888d receives (a SOCK reference clock)."
HOMEPAGE = "https://chrony-project.org/"
SECTION = "net"
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=751419260aa954499f7abaabaa882bbe"

SRC_URI = "https://chrony-project.org/releases/chrony-${PV}.tar.gz \
    file://chrony.conf \
    file://web888.conf \
"
SRC_URI[sha256sum] = "33ea8eb2a4daeaa506e8fcafd5d6d89027ed6f2f0609645c6f149b560d301706"

# Despite './configure; make; make install', chrony doesn't use autotools.
inherit systemd pkgconfig

PACKAGECONFIG ??= "${@bb.utils.filter('DISTRO_FEATURES', 'ipv6', d)}"
PACKAGECONFIG[ipv6] = ",--disable-ipv6,"

# --disable-static isn't supported by chrony's configure script.
DISABLE_STATIC = ""

do_configure() {
    ./configure --sysconfdir=${sysconfdir} --bindir=${bindir} --sbindir=${sbindir} \
                --localstatedir=${localstatedir} --datarootdir=${datadir} \
                --with-pidfile=/run/chrony/chronyd.pid \
                --chronyrundir=/run/chrony \
                --host-system=Linux \
                --without-editline --disable-sechash --disable-nts \
                --disable-privdrop --without-seccomp --disable-pps \
                ${PACKAGECONFIG_CONFARGS}
}

do_install() {
    install -d ${D}${bindir} ${D}${sbindir}
    install -m 0755 ${S}/chronyc ${D}${bindir}
    install -m 0755 ${S}/chronyd ${D}${sbindir}

    install -d ${D}${sysconfdir}
    install -m 0644 ${UNPACKDIR}/chrony.conf ${D}${sysconfdir}

    install -d ${D}${systemd_system_unitdir}/chronyd.service.d
    install -m 0644 ${S}/examples/chronyd.service ${D}${systemd_system_unitdir}/
    install -m 0644 ${UNPACKDIR}/web888.conf ${D}${systemd_system_unitdir}/chronyd.service.d/
    sed -i -e 's!/usr/sbin/!${sbindir}/!g' \
           -e 's!^EnvironmentFile=.*!EnvironmentFile=-${sysconfdir}/default/chronyd!' \
           ${D}${systemd_system_unitdir}/chronyd.service

    install -d ${D}${sysconfdir}/tmpfiles.d
    echo "d /var/lib/chrony 0755 root root -" > ${D}${sysconfdir}/tmpfiles.d/chronyd.conf
}

FILES:${PN} = "${sbindir}/chronyd ${sysconfdir} ${systemd_system_unitdir}"
CONFFILES:${PN} = "${sysconfdir}/chrony.conf"
SYSTEMD_PACKAGES = "${PN}"
SYSTEMD_SERVICE:${PN} = "chronyd.service"
RCONFLICTS:${PN} = "ntp ntimed"

PACKAGES =+ "chronyc"
FILES:chronyc = "${bindir}/chronyc"
