#!/bin/sh

DEBUG=0
CACHEDIR=$(pwd)
RFS_BASE=http://gentoo.mirrors.ovh.net

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
		case $1 in
		armel)
			ARCH=arm
		;;
		armbe)
			echo "ERROR: armbe not supported by gentoo"
			exit 1
		;;
		esac
		if [ "$ARCH" = 'x86_64' ];then
			ARCH=amd64
		fi
		SARCH=$ARCH
		shift
	;;
	--root)
		shift
		if [ "$1" != "nfs" ];then
			echo "ERROR: gentoo support only NFS"
			exit 1
		fi
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
	*)
		echo "ERROR: unknow argument $1"
		exit 1
	;;
	esac
done

debug "end of args"

if [ -z "$ARCH" ];then
	echo "ERROR: arch is not set"
	exit 1
fi

CHECK_SIG=1

found_latest()
{
	RFS_BPATH=/gentoo-distfiles/releases/$ARCH/autobuilds
	BASEURL=$RFS_BASE$RFS_BPATH
	case $ARCH in
	arm)
		SARCH=armv7a_hardfp
	;;
	arm64)
		RFS_BPATH=/gentoo-distfiles/experimental/$ARCH
		BASEURL=$RFS_BASE$RFS_BPATH
		wget -q $BASEURL/
		if [ ! -e index.html ];then
			echo "ERRROr: no index from $BASEURL"
			return 1
		fi
		STAGE3=$(grep -o '"stage3-arm64-[0-9]*.tar.bz2"' index.html | cut -d'"' -f2)
		LATEST=$STAGE3
		CHECK_SIG=0
		rm index.html
		return 0
	;;
	esac

	wget -q $BASEURL/latest-stage3-$SARCH.txt
	if [ $? -ne 0 ];then
		echo "ERROR: fail to grab $BASEURL/latest-stage3-$SARCH.txt"
		exit 1
	fi
	echo "ROOTFS_LATEST=$BASEURL/latest-stage3-$SARCH.txt"
	LATEST=$(grep -v ^# latest-stage3-$SARCH.txt | cut -d' ' -f1)
	return 0
}

found_latest || exit $?

debug "Found latest success"

wget -q $BASEURL/$LATEST.DIGESTS
if [ $? -ne 0 ];then
	echo "ERROR: fail to download $BASEURL/$LATEST.DIGESTS"
	rm latest-stage3-$SARCH.txt
	exit 1
fi

if [ $CHECK_SIG -eq 1 ];then
	wget -q $BASEURL/$LATEST.DIGESTS.asc
	if [ $? -ne 0 ];then
		echo "ERROR: fail to download $BASEURL/$LATEST.DIGESTS.asc"
		rm latest-stage3-$SARCH.txt
		rm latest-stage3-$SARCH.DIGESTS
		exit 1
	fi

	gpg --batch -q --verify $(basename $LATEST.DIGESTS.asc) >gpg.out 2>gpg.err
	if [ $? -ne 0 ];then
		echo "ERROR: GPG fail to verify"
		cat gpg.out
		cat gpg.err
		rm gpg.err gpg.out
		exit 1
	fi
	rm gpg.err gpg.out
fi

echo "ROOTFS_URL=$BASEURL/$LATEST"
echo "ROOTFS_BASE=$RFS_BASE"
echo "ROOTFS_PATH=$RFS_BPATH/$LATEST"
#cat $(basename $LATEST.DIGESTS) |
while read line
do
	echo $line | grep -q SHA512
	if [ $? -eq 0 ];then
		read line
		echo $line | grep -q "$(basename $LATEST)$"
		if [ $? -eq 0 ];then
			echo "ROOTFS_SHA512=$(echo $line | cut -d' ' -f1)"
		fi
	fi
done < $(basename $LATEST.DIGESTS)

rm $(basename $LATEST.DIGESTS)
if [ $CHECK_SIG -eq 1 ];then
	rm $(basename $LATEST.DIGESTS.asc)
fi
if [ -e latest-stage3-$SARCH.txt ];then
	rm latest-stage3-$SARCH.txt
fi
echo "PORTAGE_URL=$BASEURL/gentoo-distfiles/snapshots/portage-latest.tar.bz2"
