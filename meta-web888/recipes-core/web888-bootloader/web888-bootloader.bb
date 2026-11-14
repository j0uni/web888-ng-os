# SPDX-License-Identifier: GPL-3.0-or-later
SUMMARY = "Web-888 boot loader update: the slot's BOOT.BIN and u-boot.img"
DESCRIPTION = "Ships this build's U-Boot SPL (boot.bin) and U-Boot \
(u-boot.img) in the root slot, with web888-bootloader, which writes them \
to the SD card's FAT when the owner asks (web888d's Update tab, or SSH). \
RAUC updates only the root slots; the FAT's boot loader has no A/B, so it \
is never written by itself (docs/updates.md)."
LICENSE = "GPL-3.0-or-later"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/GPL-3.0-or-later;md5=1c76c4cc354acaac30ed4d5eefea7245"

SRC_URI = "file://web888-bootloader"
S = "${UNPACKDIR}"

# the files as deployed for the card's FAT (IMAGE_BOOT_FILES)
do_install[depends] += "virtual/bootloader:do_deploy"

do_configure[noexec] = "1"
do_compile[noexec] = "1"

do_install() {
	install -D -m 0755 ${S}/web888-bootloader ${D}${sbindir}/web888-bootloader
	d=${D}${datadir}/web888/boot
	install -d $d
	install -m 0644 ${DEPLOY_DIR_IMAGE}/boot.bin ${DEPLOY_DIR_IMAGE}/u-boot.img $d/
	(cd $d && sha256sum boot.bin u-boot.img > SHA256SUMS)
	echo "${DISTRO_VERSION}" > $d/VERSION
}

FILES:${PN} += "${datadir}/web888/boot"
PACKAGE_ARCH = "${MACHINE_ARCH}"
# the files are the target's boot loader, not code run by Linux
INSANE_SKIP:${PN} += "arch"

# fw_printenv, sha256sum, df
RDEPENDS:${PN} = "libubootenv-bin busybox"
