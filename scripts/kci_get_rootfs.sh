#!/bin/sh

DEBUG=0
CACHEDIR=$(pwd)
RFS_FILE=""
TYPE=buildroot

debug() {
	if [ $DEBUG -eq 1 ];then
		echo "$*"
	fi
}

usage() {
	$0 [-d] --arch arch --root [ramdisk|nfs] [--debian]
	exit 0
}

while [ $# -ge 1 ]
do
	case $1 in
	-d)
		DEBUG=1
		shift
	;;
	--arch)
		shift
		if [ -z "$1" ];then
			echo "ERROR: missing subargument"
			exit 1
		fi
		debug "DEBUG: set arch to $1"
		ARCH=$1
		case $ARCH in
		armbe)
			ARCH=armeb
		;;
		esac
		shift
	;;
	--root)
		shift
		case $1 in
		ramdisk)
			RFS_FILE="rootfs.cpio.gz"
		;;
		nfs)
			RFS_FILE="rootfs.tar.xz"
		;;
		*)
			exit 1
		;;
		esac
		shift
	;;
	--cachedir)
		shift
		if [ -z "$1" ];then
			echo "ERROR: missing subargument"
			exit 1
		fi
		CACHEDIR=$1
		cd "$CACHEDIR" || exit $?
		#echo "DEBUG: go to $CACHEDIR"
		shift
	;;
	--mirror)
		shift
		if [ -z "$1" ];then
			echo "ERROR: missing subargument"
			exit 1
		fi
		RFS_BASE=$1
		shift
	;;
	--debian)
		shift
		TYPE=debian/buster
		RFS_FILE="full.$RFS_FILE"
	;;
	*)
		echo "ERROR: unknow argument $1"
		exit 1
	;;
	esac
done

debug "end of args"
RFS_BASE=https://storage.kernelci.org/images/rootfs/$TYPE/

if [ -z "$ARCH" ];then
	echo "ERROR: arch is not set"
	exit 1
fi

wget -q $RFS_BASE
if [ ! -e index.html ];then
	echo "ERROR: cannot donwload index"
	exit 1
fi
case $TYPE in
'debian/buster')
DIRE=$(grep -o 'href="20[0-9a-z\.\-]*/' index.html | cut -d'"' -f2 | sort -n | tail -n1)
echo "DEBUG: $DIRE"
RFS_BPATH="/images/rootfs/debian/buster/$DIRE/$ARCH/"
;;
*)
DIRE=$(grep -o 'href="kci-20[0-9a-z\.\-]*/' index.html | cut -d'"' -f2 | sort -n | tail -n1)
RFS_BPATH="/images/rootfs/buildroot/$DIRE$ARCH/base"
;;
esac
rm index.html


echo "ROOTFS_URL=$RFS_BASE/$DIRE$ARCH/base/$RFS_FILE"
echo "ROOTFS_PATH=$RFS_BPATH/$RFS_FILE"
echo "ROOTFS_BASE=https://storage.kernelci.org"
