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
		cd $CACHEDIR
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
		shift
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
;;
*)
DIRE=$(grep -o 'href="kci-20[0-9a-z\.\-]*/' index.html | cut -d'"' -f2 | sort -n | tail -n1)
;;
esac
rm index.html
RFS_BPATH="/images/rootfs/buildroot/$DIRE$ARCH/base"


echo "ROOTFS_URL=$RFS_BASE/$DIRE$ARCH/base/$RFS_FILE"
echo "ROOTFS_PATH=$RFS_BPATH/$RFS_FILE"
echo "ROOTFS_BASE=https://storage.kernelci.org"
