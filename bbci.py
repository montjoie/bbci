#!/usr/bin/env python3

import sys
import re
import yaml
import subprocess
import os
import platform
import argparse
import xmlrpc.client
import shutil
import time
import fcntl
import pprint
import jinja2
import hashlib

###############################################################################
###############################################################################
# create a directory
def lab_create_directory(lab, directory):
    destdir = lab["datadir"]
    # check remote vs local (TODO)
    for part in directory.split("/"):
        destdir = destdir + '/' + part
        if args.debug:
            print("DEBUG: Check %s" % destdir)
        if not os.path.isdir(destdir):
            if args.debug:
                print("DEBUG: create %s" % destdir)
            os.mkdir(destdir)

###############################################################################
###############################################################################
def lab_copy(lab, src, directory):
    destdir = lab["datadir"]
    # check remote vs local (TODO)
    for part in directory.split("/"):
        destdir = destdir + '/' + part
        if args.debug:
            print("DEBUG: Check %s" % destdir)
        if not os.path.isdir(destdir):
            if args.debug:
                print("DEBUG: create %s" % destdir)
            os.mkdir(destdir)
    if args.debug:
        print("DEBUG: copy %s to %s" % (src, destdir))
    shutil.copy(src, destdir)

###############################################################################
###############################################################################
def linuxmenu(param):
    larch = param["larch"]
    kdir = param["kdir"]
    make_opts = param["make_opts"]

    pbuild = subprocess.Popen("make %s menuconfig" % make_opts, shell=True)
    outs, err = pbuild.communicate()
    return err

###############################################################################
###############################################################################
def linux_clean(param):
    larch = param["larch"]
    kdir = param["kdir"]
    make_opts = param["make_opts"]

    pbuild = subprocess.Popen("make %s clean" % make_opts, shell=True)
    outs, err = pbuild.communicate()
    return err

###############################################################################
###############################################################################
def build(param):
    larch = param["larch"]
    kdir = param["kdir"]
    make_opts = param["make_opts"] + " %s" % param["full_tgt"]
    print("BUILD: %s to %s" % (larch, kdir))
    if args.debug:
        print("DEBUG: makeopts=%s" % make_opts)

    if args.noact:
        print("Will run make %s" % make_opts)
        return 0

    logdir = os.path.expandvars(tc["config"]["logdir"])
    if not os.path.exists(logdir):
        os.mkdir(logdir)

    if not args.noclean:
        err = linux_clean(param)
        if err != 0:
            print("WARNING: make clean fail")

    if args.nolog:
        logfile = sys.stdout
    else:
        logfile = open("%s/%s.log" % (logdir, param["targetname"]), 'w')

    if args.quiet:
        pbuild = subprocess.Popen("make %s" % make_opts, shell=True, stdout=subprocess.DEVNULL)
    else:
        pbuild = subprocess.Popen("make %s 2>&1" % make_opts, shell=True, stdout=logfile)
    outs, err = pbuild.communicate()

    builds[param["targetname"]] = {}
    if err is None and pbuild.returncode == 0:
        if args.debug:
            print("DEBUG: build success")
    else:
        builds[param["targetname"]]["result"] = 'FAIL'
        if not args.nolog:
            logfile.close()
        return err

    if "modules_dir" in param:
        modules_dir = param["modules_dir"]
        if os.path.isdir(modules_dir):
            if args.debug:
                print("DEBUG: clean old %s" % modules_dir)
            if not args.noact:
                shutil.rmtree(modules_dir)
        os.mkdir(modules_dir)
        if args.debug:
            print("DEBUG: do modules_install")
        if args.quiet:
            pbuild = subprocess.Popen("make %s modules_install" % make_opts, shell=True, stdout=subprocess.DEVNULL)
        else:
            pbuild = subprocess.Popen("make %s modules_install 2>&1" % make_opts, shell=True, stdout=logfile)
        outs, err = pbuild.communicate()
    if not args.nolog:
        logfile.close()

    if err is None and pbuild.returncode == 0:
        builds[param["targetname"]]["result"] = 'PASS'
    else:
        builds[param["targetname"]]["result"] = 'FAIL'
    return err

###############################################################################
###############################################################################
def boot(param):
    larch = param["larch"]
    subarch = param["subarch"]
    flavour = param["flavour"]
    kdir = param["kdir"]
    sourcename = param["sourcename"]
    global qemu_boot_id

    logdir = os.path.expandvars(tc["config"]["logdir"])
    if not os.path.exists(logdir):
        os.mkdir(logdir)

    arch_endian = None

    if os.path.exists("%s/.config" % kdir):
        kconfig = open("%s/.config" % kdir)
        kconfigs = kconfig.read()
        kconfig.close()
        if re.search("CONFIG_CPU_BIG_ENDIAN=y", kconfigs):
            endian = "big"
        else:
            endian = "little"
        if re.search("CONFIG_NIOS2=", kconfigs):
            arch = "nios2"
            arch_endian = "nios2"
            qarch = "nios2"
        if re.search("CONFIG_XTENSA=", kconfigs):
            arch = "xtensa"
            arch_endian = "xtensa"
            qarch = "xtensa"
        if re.search("CONFIG_SPARC32=", kconfigs):
            arch = "sparc"
            arch_endian = "sparc"
            qarch = "sparc"
        if re.search("CONFIG_SPARC64=", kconfigs):
            arch = "sparc64"
            arch_endian = "sparc64"
        qarch = "sparc64"
        if re.search("CONFIG_ARM=", kconfigs):
            arch = "arm"
            qarch = "arm"
            if re.search("CONFIG_CPU_BIG_ENDIAN=y", kconfigs):
                arch_endian = "armbe"
            else:
                arch_endian = "armel"
        if re.search("CONFIG_ARM64=", kconfigs):
            arch = "arm64"
            arch_endian = "arm64"
            qarch = "aarch64"
        if re.search("CONFIG_ARC=", kconfigs):
            arch = "arc"
            arch_endian = "arc"
            qarch = None
        if re.search("CONFIG_MIPS=", kconfigs):
            if re.search("CONFIG_64BIT=y", kconfigs):
                arch = "mips64"
                qarch = "mips64"
                if endian == 'big':
                    arch_endian = "mips64be"
                else:
                    arch_endian = 'mips64el'
            else:
                arch = "mips"
                qarch = "mips"
                if endian == 'big':
                    arch_endian = "mipsbe"
                else:
                    arch_endian = 'mipsel'
                    qarch = "mipsel"
        if re.search("CONFIG_ALPHA=", kconfigs):
            arch = "alpha"
            arch_endian = "alpha"
            qarch = "alpha"
        if re.search("CONFIG_PPC=", kconfigs):
            arch = "powerpc"
            arch_endian = "powerpc"
            qarch = "ppc"
        if re.search("CONFIG_PPC64=", kconfigs):
            arch = "powerpc64"
            arch_endian = "ppc64"
            qarch = "ppc64"
        if re.search("CONFIG_OPENRISC=", kconfigs):
            arch = "openrisc"
            arch_endian = "openrisc"
            qarch = "or1k"
        if re.search("CONFIG_MICROBLAZE=", kconfigs):
            arch = "microblaze"
            if re.search("CONFIG_CPU_BIG_ENDIAN=y", kconfigs):
                arch_endian = "microblaze"
                qarch = "microblaze"
            else:
                arch_endian = "microblazeel"
                qarch = "microblazeel"
        if re.search("CONFIG_X86_64=", kconfigs):
            arch = "x86_64"
            arch_endian = "x86_64"
            qarch = "x86_64"
        if re.search("CONFIG_X86=", kconfigs) and not re.search("CONFIG_X86_64=", kconfigs):
            arch = "x86"
            arch_endian = "x86"
            qarch = "i386"
    else:
        kconfigs = ""
        # detect from the given larch
        if larch == "x86_64":
            arch = "x86_64"
            arch_endian = "x86_64"
            qarch = "x86_64"
            endian = "little"
        if larch == "arm":
            arch = "arm"
            arch_endian = "armel"
            qarch = "arm"
            endian = "little"
        if larch == "arm64":
            arch = "arm64"
            arch_endian = "arm64"
            qarch = "aarch64"
            endian = "little"

    if arch_endian is None:
        print("ERROR: Missing endian arch")
        return 1

    print("INFO: arch is %s, Linux arch is %s, QEMU arch is %s, archendian is %s" % (arch, larch, qarch, arch_endian))

    # TODO check RAMFS and INITRD and MODULES and DEVTMPFS_MOUNT

    #TODO check error
    if os.path.isdir(".git"):
        git_describe = subprocess.check_output('git describe --always', shell=True).strip().decode("utf-8")
        git_lastcommit = subprocess.check_output('git rev-parse HEAD', shell=True).strip().decode("utf-8")
        git_branch = subprocess.check_output('git rev-parse --abbrev-ref HEAD', shell=True).strip().decode("utf-8")
    elif os.path.exists("Makefile"):
        VERSION = subprocess.check_output('grep ^VERSION Makefile | sed "s,.* ,,"', shell=True).strip().decode("utf-8")
        PATCHLEVEL = subprocess.check_output('grep ^PATCHLEVEL Makefile | sed "s,.* ,,"', shell=True).strip().decode("utf-8")
        SUBLEVEL = subprocess.check_output('grep ^SUBLEVEL Makefile | sed "s,.* ,,"', shell=True).strip().decode("utf-8")
        EXTRAVERSION = subprocess.check_output('grep ^EXTRAVERSION Makefile | sed "s,.* ,,"', shell=True).strip().decode("utf-8")
        git_describe = "%s.%s.%s%s" % (VERSION, PATCHLEVEL, SUBLEVEL, EXTRAVERSION)
        git_lastcommit = "None"
        git_branch = "None"
    else:
        git_describe = "None"
        git_lastcommit = "None"
        git_branch = "None"

    # generate modules.tar.gz
    #TODO check error
    if "modules_dir" in param:
        modules_dir = param["modules_dir"]
    else:
        modules_dir = "%s/fake" % builddir
        if os.path.exists(modules_dir):
            shutil.rmtree(modules_dir)
        os.mkdir(modules_dir)
        os.mkdir("%s/lib/" % modules_dir)
        os.mkdir("%s/lib/modules" % modules_dir)
    if args.quiet:
        pbuild = subprocess.Popen("cd %s && tar czf modules.tar.gz lib" % modules_dir, shell=True, stdout=subprocess.DEVNULL)
        outs, err = pbuild.communicate()
    else:
        pbuild = subprocess.Popen("cd %s && tar czf modules.tar.gz lib" % modules_dir, shell=True)
        outs, err = pbuild.communicate()
    if err is not None and err != 0:
        print("ERROR: fail to generate modules.tar.gz in %s (err=%d)" % (modules_dir, err))
        print(outs)
        return 1

    for device in t["templates"]:
        if "devicename" in device:
            devicename = device["devicename"]
        else:
            devicename = device["devicetype"]
        if "larch" in device:
            device_larch = device["larch"]
        else:
            device_larch = device["arch"]
        if device_larch != larch:
            if args.debug:
                print("SKIP: %s (wrong larch %s vs %s)" % (devicename, device_larch, larch))
            continue
        if device["arch"] != arch:
            if args.debug:
                print("SKIP: %s arch: %s vs %s" % (devicename, device["arch"], arch))
            continue
        print("==============================================")
        print("CHECK: %s" % devicename)
        # check config requirements
        skip = False
        if "configs" in device and device["configs"] is not None and kconfigs != "":
            for config in device["configs"]:
                if "name" not in config:
                    print("Invalid config")
                    print(config)
                    continue
                if not re.search(config["name"], kconfigs):
                    if "type" in config and config["type"] == "mandatory":
                        print("\tSKIP: missing %s" % config["name"])
                        skip = True
                    else:
                        print("\tINFO: missing %s" % config["name"])
                else:
                    print("DEBUG: found %s" % config["name"])
        if skip:
            continue
        goodtag = True
        if args.dtag:
            for tag in args.dtag.split(","):
                if tag == device["devicetype"]:
                    tagfound = True
                    continue
                if args.debug:
                    print("DEBUG: check tag %s" % tag)
                if "tags" not in device:
                    print("SKIP: no tag")
                    gootdtag = False
                    continue
                tagfound = False
                for dtag in device["tags"]:
                    if tag == "qemu":
                        if "qemu" in device:
                            tagfound = True
                    if tag == "noqemu":
                        if "qemu" not in device:
                            tagfound = True
                    if args.debug:
                        print("DEBUG: found device tag %s" % dtag)
                    if dtag == tag:
                        tagfound = True
                if not tagfound:
                    print("SKIP: cannot found tag %s" % tag)
                    goodtag = False
        if not goodtag:
            continue
        kerneltype = "image"
        kernelfile = device["kernelfile"]
        if kernelfile == "zImage":
            kerneltype = "zimage"
        if kernelfile == "uImage":
            kerneltype = "uimage"
        # check needed files
        if "kernelfile" not in device:
            print("ERROR: missing kernelfile")
            continue
        if args.debug:
            print("DEBUG: seek %s" % device["kernelfile"])
        kfile = "%s/arch/%s/boot/%s" % (kdir, larch, device["kernelfile"])
        if os.path.isfile(kfile):
            if args.debug:
                print("DEBUG: found %s" % kfile)
        else:
            if args.debug:
                print("DEBUG: %s not found" % kfile)
            kfile = "%s/%s" % (kdir, device["kernelfile"])
            if os.path.isfile(kfile):
                if args.debug:
                    print("DEBUG: found %s" % kfile)
            else:
                print("SKIP: no kernelfile")
                continue
        # Fill lab indepedant data
        jobdict = {}
        jobdict["KERNELFILE"] = kernelfile
        with open(kfile, "rb") as fkernel:
            jobdict["KERNEL_SHA256"] = hashlib.sha256(fkernel.read()).hexdigest()
        jobdict["DEVICETYPE"] = device["devicetype"]
        jobdict["MACH"] = device["mach"]
        jobdict["ARCH"] = device["arch"]
        jobdict["PATH"] = "%s/%s/%s/%s" % (sourcename, larch, subarch, flavour)
        jobdict["ARCHENDIAN"] = arch_endian
        jobdict["GIT_DESCRIBE"] = git_describe
        jobdict["KVERSION"] = git_describe
        jobdict["K_DEFCONFIG"] = param["configbase"]
        jobdict["KENDIAN"] = endian
        jobdict["KERNELTYPE"] = kerneltype
        jobdict["GIT_LASTCOMMIT"] = git_lastcommit
        jobdict["GIT_BRANCH"] = git_branch
        jobdict["LAVA_BOOT_TYPE"] = kerneltype
        jobdict["initrd_path"] = "/rootfs/%s/rootfs.cpio.gz" % arch_endian
        jobdict["test"] = "True"
        jobdict["rootfs_method"] = "ramdisk"
        if "boot-method" in device:
            jobdict["boot_method"] = device["boot-method"]
        # ROOTFS cpio.gz are for ramdisk, tar.xz for nfs, ext4.gz for NBD
        if args.rootfs == "nfs":
            jobdict["rootfs_method"] = "nfs"
            jobdict["boot_commands"] = "nfs"
            if "qemu" in device:
                jobdict["boot_method"] = "qemu-nfs"
                jobdict["boot_media"] = "nfs"
                jobdict["initrd_path"] = "/initrd/nfs-%s/rootfs.cpio.gz" % arch_endian
                jobdict["rootfs_path"] = "/rootfs/%s/rootfs.tar.xz" % arch_endian
            else:
                # default
                #jobdict["boot_method"] = "u-boot"
                #jobdict["boot_to"] = "tftp"
                jobdict["boot_media"] = "nfs"
                jobdict["rootfs_path"] = "/rootfs/%s/rootfs.tar.xz" % arch_endian
        elif args.rootfs == "nbd":
            jobdict["rootfs_method"] = "nbd"
            if "qemu" in device:
                print("ERROR: NBD for qemu is unsupported")
                continue
            jobdict["boot_commands"] = "nbd"
            jobdict["boot_to"] = "nbd"
            jobdict["rootfs_path"] = "/rootfs/%s/rootfs.ext4.gz" % arch_endian

        spetial = param["toolchaininuse"]
        if args.configoverlay:
            spetial += "+%s" % args.configoverlay
        jobdict["JOBNAME"] = "AUTOTEST %s %s/%s/%s/%s on %s (%s,root=%s)" % (git_describe, sourcename, larch, subarch, flavour, devicename, spetial, jobdict["rootfs_method"])
        nonetwork = False
        for dtag in device["tags"]:
            if dtag == "nonetwork":
                nonetwork = True
            if dtag == "noinitrd" or dtag == 'rootonsd':
                jobdict["image_arg"] = '-drive format=raw,if=sd,file={ramdisk}'
                jobdict["initrd_path"] = "/rootfs/%s/rootfs.ext2" % arch_endian
            if dtag == "notests" or dtag == "nostorage" or args.testsuite is None:
                jobdict["test"] = "False"
                if args.debug:
                    print("DEBUG: Remove test from job")
        if "qemu" in device:
            print("\tQEMU")
            jobdict["qemu_arch"] = qarch
            if "netdevice" in device["qemu"]:
                jobdict["qemu_netdevice"] = "tap"
            if "model" in device["qemu"]:
                jobdict["qemu_model"] = device["qemu"]["model"]
            if "machine" in device["qemu"]:
                jobdict["qemu_machine"] = device["qemu"]["machine"]
            if "cpu" in device["qemu"]:
                jobdict["qemu_cpu"] = device["qemu"]["cpu"]
            if "memory" in device["qemu"]:
                jobdict["qemu_memory"] = device["qemu"]["memory"]
            if "console_device" in device["qemu"]:
                jobdict["console_device"] = device["qemu"]["console_device"]
            if "guestfs_interface" in device["qemu"]:
                jobdict["guestfs_interface"] = device["qemu"]["guestfs_interface"]
            if "guestfs_driveid" in device["qemu"]:
                jobdict["guestfs_driveid"] = device["qemu"]["guestfs_driveid"]
            if "extra_options" in device["qemu"]:
                jobdict["qemu_extra_options"] = device["qemu"]["extra_options"]
                # with root on nfs/nbd, tests are not set on a storage, so we need to filter them
                if args.rootfs == "nfs" or args.rootfs == "nbd":
                    newextrao = []
                    for extrao in device["qemu"]["extra_options"]:
                        if re.search("lavatest", extrao):
                            continue
                        newextrao.append(extrao)
                    jobdict["qemu_extra_options"] = newextrao
            if "extra_options" not in device["qemu"]:
                jobdict["qemu_extra_options"] = []
            netoptions = "ip=dhcp"
            if nonetwork:
                netoptions = ""
            jobdict["qemu_extra_options"].append("-append '%s %s'" % (device["qemu"]["append"], netoptions))
        templateLoader = jinja2.FileSystemLoader(searchpath=templatedir)
        templateEnv = jinja2.Environment(loader=templateLoader)
        if "qemu" in device:
            template = templateEnv.get_template("defaultqemu.jinja2")
        else:
            template = templateEnv.get_template("default.jinja2")
        if "doqemu" in param:
            if "qemu" not in device:
                return 0
            failure = None
            # The exec here permits a working qp.terminate()
            qemu_cmd = "exec qemu-system-%s -kernel %s -nographic -machine %s" % (qarch, kfile, device["qemu"]["machine"])
            if "qemu_bios_path" in tc["config"]:
                qemu_cmd += " -L %s" % os.path.expandvars(tc["config"]["qemu_bios_path"])
            if "qemu_bin_path" in tc["config"]:
                os.environ["PATH"] = "%s:%s" % (os.path.expandvars(tc["config"]["qemu_bin_path"]), os.environ["PATH"])
            if "extra_options" in device["qemu"]:
                for extrao in device["qemu"]["extra_options"]:
                    qemu_cmd += " %s" % extrao
            qemu_cmd += " -append '%s'" % device["qemu"]["append"]
            if re.search("CONFIG_SERIAL_PMACZILOG=", kconfigs) and re.search("CONFIG_SERIAL_PMACZILOG_TTYS=y", kconfigs):
                print("INFO: PMACZILOG console hack")
                qemu_cmd = qemu_cmd.replace("console=ttyPZ0", "console=ttyS0")
            #qemu_cmd += " -drive format=qcow2,file=$HOME/bbci/flash.bin"
            if "dtb" in device:
                dtbfile = "%s/arch/%s/boot/dts/%s" % (kdir, larch, device["dtb"])
                if not os.path.isfile(dtbfile):
                    #try at base directory
                    dtbfile = "%s/%s" % (kdir, device["dtb"])
                    if not os.path.isfile(dtbfile):
                        # retry with basename
                        dtbfile = "%s/%s" % (kdir, os.path.basename(device["dtb"]))
                        if not os.path.isfile(dtbfile):
                            print("SKIP: no dtb at %s" % dtbfile)
                            continue
                with open(dtbfile, "rb") as fdtb:
                    jobdict["DTB_SHA256"] = hashlib.sha256(fdtb.read()).hexdigest()
                qemu_cmd += " -dtb %s" % dtbfile
            if "memory" in device["qemu"]:
                qemu_cmd += " -m %s" % device["qemu"]["memory"]
            if "cpu" in device["qemu"]:
                qemu_cmd += " -cpu %s" % device["qemu"]["cpu"]
            if "model" in device["qemu"]:
                qemu_cmd += " -net nic,%s,macaddr=52:54:00:12:34:58 -net user" % device["qemu"]["model"]
            if not os.path.isfile("%s/disk.img" % cachedir):
                subprocess.run("qemu-img create -f qcow2 %s/disk.img 10M" % cachedir, shell=True)
            guestfs_interface = 'ide'
            if "guestfs_interface" in device["qemu"]:
                guestfs_interface = device["qemu"]["guestfs_interface"]
            qemu_cmd += " -drive format=qcow2,file=%s/disk.img,if=%s,id=lavatest" % (cachedir, guestfs_interface)
            # Add initrd
            for lab in tlabs["labs"]:
                if "disabled" in lab and lab["disabled"]:
                    continue
                datadir = lab["datadir"]
                break
            qemu_cmd += " -initrd %s/rootfs/%s/rootfs.cpio.gz" % (datadir, arch_endian)
            print(qemu_cmd)
            qp = subprocess.Popen(qemu_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

            flags = fcntl.fcntl(qp.stdout, fcntl.F_GETFL)
            flags = flags | os.O_NONBLOCK
            fcntl.fcntl(qp.stdout, fcntl.F_SETFL, flags)
            flags = fcntl.fcntl(qp.stderr, fcntl.F_GETFL)
            flags = flags | os.O_NONBLOCK
            fcntl.fcntl(qp.stderr, fcntl.F_SETFL, flags)

            qlogfile = open("%s/%s-%s-%s.log" % (logdir, device["name"].replace('/', '_'), sourcename, param["targetname"]), 'w')
            poweroff_done = False
            qtimeout = 0
            lastline = ""
            normal_halt = False
            ret = 0
            last_error_line = ""
            while True:
                try:
                    line = "x"
                    got_line = False
                    while line != "":
                        line = qp.stdout.readline().decode('UTF8')
                        if line != "":
                            print(line, end='')
                            qlogfile.write(line)
                            got_line = True
                        if not got_line:
                            qtimeout = qtimeout + 1
                        if re.search("^Kernel panic - not syncing", line):
                            qtimeout = 490
                            last_error_line = line
                            failure = "panic"
                        if re.search("end Kernel panic - not syncing", line):
                            qtimeout = 490
                            failure = "panic"
                        if re.search("/ #", line) and not poweroff_done:
                            qp.stdin.write(b'poweroff\r\n')
                            qp.stdin.flush()
                            poweroff_done = True
                        # System Halted, OK to turn off power
                        if line == "Machine halt..." or re.search("reboot: System halted", line) or re.search("reboot: power down", line):
                            if args.debug:
                                print("DEBUG: detected machine halt")
                            normal_halt = True
                            qtimeout = 490
                except ValueError:
                    time.sleep(0.1)
                    qtimeout = qtimeout + 1
                try:
                    line = "x"
                    while line != "":
                        line = qp.stderr.readline().decode('UTF8').strip()
                        if line != "":
                            print(line)
                            last_error_line = line
                except ValueError:
                    time.sleep(0.1)
                time.sleep(0.2)
                if qtimeout > 500:
                    qp.terminate()
                    if normal_halt:
                        ret = 0
                        break
                    print("ERROR: QEMU TIMEOUT!")
                    ret = 1
                    if failure is None:
                        failure = "timeout"
                    break
                ret = qp.poll()
                if ret is not None:
                    # grab last stderr
                    try:
                        line = "x"
                        while line != "":
                            line = qp.stderr.readline().decode('UTF8').strip()
                            if line != "":
                                print(line)
                                last_error_line = line
                    except ValueError:
                        time.sleep(0.1)
                    ret = qp.returncode
                    if ret != 0:
                        failure = "Code: %d" % ret
                    break
            qlogfile.close()
            if "qemu" not in boots:
                boots["qemu"] = {}
            qemu_boot_id = qemu_boot_id + 1
            boots["qemu"][qemu_boot_id] = {}
            boots["qemu"][qemu_boot_id]["devicename"] = devicename
            boots["qemu"][qemu_boot_id]["arch"] = arch
            boots["qemu"][qemu_boot_id]["targetname"] = param["targetname"]
            boots["qemu"][qemu_boot_id]["sourcename"] = sourcename
            if ret == 0:
                boots["qemu"][qemu_boot_id]["result"] = 'PASS'
            else:
                boots["qemu"][qemu_boot_id]["result"] = 'FAIL'
                boots["qemu"][qemu_boot_id]["failure"] = failure
                if last_error_line != "":
                    boots["qemu"][qemu_boot_id]["error"] = last_error_line
            continue
            return ret

        # now try to boot on LAVA
        for lab in tlabs["labs"]:
            send_to_lab = False
            print("\tCheck %s on %s" % (devicename, lab["name"]))
            if "disabled" in lab and lab["disabled"]:
                continue
        # LAB dependant DATA
            server = xmlrpc.client.ServerProxy(lab["lavauri"])
            devlist = server.scheduler.devices.list()
            for labdevice in devlist:
                if labdevice["type"] == device["devicetype"]:
                    send_to_lab = True
            alia_list = server.scheduler.aliases.list()
            for alias in alia_list:
                if alias == device["devicetype"]:
                    send_to_lab = True
            if not send_to_lab:
                print("\tSKIP: not found")
                continue
            #copy files
            data_relpath = "%s/%s/%s/%s" % (sourcename, larch, subarch, flavour)
            lab_create_directory(lab, data_relpath)
            datadir = lab["datadir"]
            destdir = "%s/%s/%s/%s/%s" % (datadir, sourcename, larch, subarch, flavour)
            # copy kernel
            if args.debug:
                print("DEBUG: copy %s" % kfile)
            lab_copy(lab, kfile, data_relpath)
            # copy dtb
            # TODO dtb metadata
            if "dtb" in device:
                jobdict["dtb_path"] = "/%s/%s/%s/%s/dts/%s" % (sourcename, larch, subarch, flavour, device["dtb"])
                jobdict["DTB"] = device["dtb"]
                dtbfile = "%s/arch/%s/boot/dts/%s" % (kdir, larch, device["dtb"])
                dtbsubdir = device["dtb"].split('/')
                dtb_relpath = "/dts/"
                if len(dtbsubdir) > 1:
                    dtb_relpath = dtb_relpath + dtbsubdir[0]
                if not os.path.isfile(dtbfile):
                    #try at base directory
                    dtbfile = "%s/%s" % (kdir, device["dtb"])
                    if not os.path.isfile(dtbfile):
                        # retry with basename
                        dtbfile = "%s/%s" % (kdir, os.path.basename(device["dtb"]))
                        if not os.path.isfile(dtbfile):
                            print("SKIP: no dtb at %s" % dtbfile)
                            continue
                lab_copy(lab, dtbfile, "%s/%s" % (data_relpath, dtb_relpath))
                with open(dtbfile, "rb") as fdtb:
                    jobdict["DTB_SHA256"] = hashlib.sha256(fdtb.read()).hexdigest()
            # modules.tar.gz
            lab_copy(lab, "%s/modules.tar.gz" % modules_dir, data_relpath)
            with open("%s/modules.tar.gz" % modules_dir, "rb") as fmodules:
                jobdict["MODULES_SHA256"] = hashlib.sha256(fmodules.read()).hexdigest()
            # final job
            if not os.path.isdir(outputdir):
                os.mkdir(outputdir)
            if not os.path.isdir("%s/%s" % (outputdir, lab["name"])):
                os.mkdir("%s/%s" % (outputdir, lab["name"]))
            result = subprocess.check_output("chmod -R o+rX %s" % datadir, shell=True)
            #print(result.decode("UTF-8"))
            jobdict["BOOT_FQDN"] = lab["datahost_baseuri"]
            jobdict["ROOT_FQDN"] = lab["rootfs_baseuri"]
            jobt = template.render(jobdict)
            # HACK CONFIG_SERIAL_PMACZILOG=y CONFIG_SERIAL_PMACZILOG_TTYS=y
            if re.search("CONFIG_SERIAL_PMACZILOG=", kconfigs) and re.search("CONFIG_SERIAL_PMACZILOG_TTYS=y", kconfigs):
                print("INFO: PMACZILOG console hack")
                jobt = jobt.replace("console=ttyPZ0", "console=ttyS0")
            fw = open("%s/job-%s.yaml" % (cachedir, devicename), "w")
            fw.write(jobt)
            fw.close()
            if not args.noact:
                jobid = server.scheduler.jobs.submit(jobt)
                print(jobid)
                if lab["name"] not in boots:
                    boots[lab["name"]] = {}
                boots[lab["name"]][jobid] = {}
                boots[lab["name"]][jobid]["devicename"] = devicename
            else:
                print("\tSKIP: send job to %s" % lab["name"])
    return 0

###############################################################################
###############################################################################
def enable_config(param, econfig):
    rawconfig = econfig.split("=")[0]

    if args.debug:
        print("=================================================== %s" % econfig)
        print("DEBUG: Try enable config %s" % econfig)
        subprocess.run("cp %s/.config %s/.config.old" % (param["kdir"], param["kdir"]), shell=True)
    with open("%s/.config" % param["kdir"], 'r') as fconfig:
        wconfig = fconfig.read()
    if re.search("=", econfig):
        if re.search("%s" % econfig, wconfig):
            if args.debug:
                print("DEBUG: %s is already enabled" % econfig)
            return 0
        wconfig = re.sub("# %s is not set" % rawconfig, "%s" % econfig, wconfig)
        # handle case CONFIG="" replaced by CONFIG="xxxx"
        wconfig = re.sub("%s=.*" % rawconfig, "%s" % econfig, wconfig)
    else:
        if re.search("%s=" % econfig, wconfig):
            if args.debug:
                print("DEBUG: %s is already enabled" % econfig)
            return 0
        wconfig = re.sub("# %s is not set" % rawconfig, "%s=y" % econfig, wconfig)
    with open("%s/.config" % param["kdir"], 'w') as fconfig:
        fconfig.write(wconfig)
    make_opts = param["make_opts"]
    if args.debug:
        subprocess.run("diff -u %s/.config.old %s/.config" % (param["kdir"], param["kdir"]), shell=True)
    pbuild = subprocess.run("make %s olddefconfig > /dev/null" % make_opts, shell=True)
    if args.debug:
        subprocess.run("diff -u %s/.config.old %s/.config" % (param["kdir"], param["kdir"]), shell=True)

###############################################################################
###############################################################################
def disable_config(param, dconfig):
    if args.debug:
        print("=================================================== %s" % dconfig)
        subprocess.run("cp %s/.config %s/.config.old" % (param["kdir"], param["kdir"]), shell=True)
    with open("%s/.config" % param["kdir"], 'r') as fconfig:
        wconfig = fconfig.read()
        if not re.search("%s=" % dconfig, wconfig):
            print("DEBUG: %s is already disabled" % dconfig)
            return 0
    wconfig = re.sub("%s.*" % dconfig, "# %s is not set" % dconfig, wconfig)
    with open("%s/.config" % param["kdir"], 'w') as fconfig:
        fconfig.write(wconfig)
    if args.debug:
        subprocess.run("diff -u %s/.config.old %s/.config" % (param["kdir"], param["kdir"]), shell=True)
    make_opts = param["make_opts"]
    pbuild = subprocess.run("make %s olddefconfig" % make_opts, shell=True)
    # verify it is still disabled
    with open("%s/.config" % param["kdir"], 'r') as fconfig:
        wconfig = fconfig.read()
        if re.search("^%s=" % dconfig, wconfig):
            print("BADDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD")

###############################################################################
###############################################################################
def genconfig(sourcedir, param, defconfig):
    os.chdir(sourcedir)

    make_opts = param["make_opts"]
    if args.noact:
        print("Will do make %s %s" % (make_opts, defconfig))
        return 0
    if defconfig == "randconfig" and args.randconfigseed is not None:
        os.environ["KCONFIG_SEED"] = args.randconfigseed

    logdir = os.path.expandvars(tc["config"]["logdir"])
    if not os.path.exists(logdir):
        os.mkdir(logdir)

    if args.nolog:
        logfile = sys.stdout
    else:
        logfile = open("%s/%s.log" % (logdir, param["targetname"]), 'w')

    if args.quiet:
        pbuild = subprocess.Popen("make %s %d" % (make_opts, defconfig), shell=True, stdout=subprocess.DEVNULL)
    else:
        pbuild = subprocess.Popen("make %s %s 2>&1" % (make_opts, defconfig), shell=True, stdout=logfile)
    outs, err = pbuild.communicate()

    if args.configoverlay:
        for coverlay in args.configoverlay.split(","):
            if coverlay == "vanilla":
                if args.debug:
                    print("DEBUG: skip all config overlays")
                return 0

    shutil.copy("%s/.config" % param["kdir"], "%s/.config.def" % param["kdir"])
    # add needed options for LAVA
    if args.debug:
        print("DEBUG: add LAVA configs")
    enable_config(param, "CONFIG_BLK_DEV_INITRD")
    enable_config(param, "CONFIG_BLK_DEV_RAM=y")
    enable_config(param, "CONFIG_DEVTMPFS=y")
    enable_config(param, "CONFIG_DEVTMPFS_MOUNT=y")
    enable_config(param, "CONFIG_MODULES=y")
    enable_config(param, "CONFIG_DEVTMPFS_MOUNT")
    enable_config(param, "CONFIG_IKCONFIG")
    enable_config(param, "CONFIG_IKCONFIG_PROC")

    if args.configoverlay:
        for coverlay in args.configoverlay.split(","):
            if coverlay == "nomodule":
                subprocess.run("sed -i 's,=m$,=y,' %s/.config" % param["kdir"], shell=True)
            if coverlay == "fullsound":
                enable_config(param, "CONFIG_SOUND")
                subprocess.run("sed -i 's,^#[[:space:]]\(.*SND.*\) is not set,\\1=m,' %s/.config" % param["kdir"], shell=True)
                pbuild = subprocess.run("make %s olddefconfig" % make_opts, shell=True)
                subprocess.run("sed -i 's,^#[[:space:]]\(.*SND.*\) is not set,\\1=m,' %s/.config" % param["kdir"], shell=True)
                pbuild = subprocess.run("make %s olddefconfig" % make_opts, shell=True)
                subprocess.run("sed -i 's,^#[[:space:]]\(.*SND.*\) is not set,\\1=m,' %s/.config" % param["kdir"], shell=True)
                pbuild = subprocess.run("make %s olddefconfig" % make_opts, shell=True)
            if coverlay == "fulldrm":
                subprocess.run("sed -i 's,^#[[:space:]]\(.*DRM.*\) is not set,\\1=m,' %s/.config" % param["kdir"], shell=True)
                pbuild = subprocess.run("make %s olddefconfig" % make_opts, shell=True)
            if coverlay == "fullcrypto":
                enable_config(param, "CONFIG_CRYPTO_CBC=y")
                enable_config(param, "CONFIG_MD=y")
                enable_config(param, "CONFIG_BLK_DEV_DM=y")
                enable_config(param, "CONFIG_BLK_DEV_LOOP=y")
                enable_config(param, "CONFIG_DM_CRYPT=m")
                if args.debug:
                    subprocess.run("cp %s/.config %s/.config.old" % (param["kdir"], param["kdir"]), shell=True)
                subprocess.run("sed -i 's,^#[[:space:]]\(.*CRYPTO.*\) is not set,\\1=m,' %s/.config" % param["kdir"], shell=True)
                #subprocess.run("sed -i 's,^CONFIG_CRYPTO_MANAGER_DISABLE_TESTS=y,# CONFIG_CRYPTO_MANAGER_DISABLE_TESTS is not set,' %s/.config" % param["kdir"], shell=True)
                disable_config(param, "CONFIG_CRYPTO_MANAGER_DISABLE_TESTS")
                enable_config(param, "CONFIG_CRYPTO_MANAGER_EXTRA_TESTS=y")
                enable_config(param, "CONFIG_CRYPTO_USER=y")
                enable_config(param, "CONFIG_CRYPTO_USER_API=y")
                enable_config(param, "CONFIG_CRYPTO_USER_API_RNG=y")
                enable_config(param, "CONFIG_CRYPTO_ANSI_CPRNG=y")
                enable_config(param, "CONFIG_CRYPTO_DEV_AMLOGIC_GXL_DEBUG=y")
                enable_config(param, "CONFIG_CRYPTO_DEV_SUN8I_CE_DEBUG=y")
                enable_config(param, "CONFIG_CRYPTO_DEV_SUN8I_SS_DEBUG=y")
                enable_config(param, "CONFIG_CRYPTO_DEV_SUN4I_SS_PRNG=y")
                if args.debug:
                    subprocess.run("diff -u %s/.config.old %s/.config" % (param["kdir"], param["kdir"]), shell=True)
                continue
            if coverlay == "fulldebug":
                if args.debug:
                    subprocess.run("cp %s/.config %s/.config.old" % (param["kdir"], param["kdir"]), shell=True)
                subprocess.run("sed -i 's,^#[[:space:]]\(.*DEBUG.*\) is not set,\\1=y,' %s/.config" % param["kdir"], shell=True)
                if args.debug:
                    subprocess.run("diff -u %s/.config.old %s/.config" % (param["kdir"], param["kdir"]), shell=True)
                continue
            if coverlay == "nfs":
                subprocess.run("sed -i 's,^#[[:space:]]\(.*DWMAC.*\) is not set,\\1=y,' %s/.config" % param["kdir"], shell=True)
                subprocess.run("sed -i 's,^#[[:space:]]\(.*STMMAC.*\) is not set,\\1=y,' %s/.config" % param["kdir"], shell=True)
                subprocess.run("sed -i 's,^\(.*DWMAC.*\)=m,\\1=y,' %s/.config" % param["kdir"], shell=True)
                subprocess.run("sed -i 's,^\(.*STMMAC.*\)=m,\\1=y,' %s/.config" % param["kdir"], shell=True)
                enable_config(param, "CONFIG_STMMAC_PLATFORM=y")
                enable_config(param, "CONFIG_STMMAC_ETH=y")
                enable_config(param, "CONFIG_DWMAC_MESON=y")
                enable_config(param, "CONFIG_DWMAC_SUNXI=y")
                enable_config(param, "CONFIG_DWMAC_SUN8I=y")
                enable_config(param, "CONFIG_USB_NET_SMSC95XX=y")
                enable_config(param, "CONFIG_IP_PNP_DHCP=y")
                enable_config(param, "CONFIG_NFS_V3=y")
                enable_config(param, "CONFIG_NFS_V4=y")
                enable_config(param, "CONFIG_ROOT_NFS=y")
            if coverlay == "cpu_be":
                enable_config(param, "CONFIG_CPU_BIG_ENDIAN=y")
            if coverlay == "cpu_el":
                disable_config(param, "CONFIG_CPU_BIG_ENDIAN=y")
            if coverlay == "wifi":
                enable_config(param, "CONFIG_WLAN=y")
                enable_config(param, "CONFIG_CFG80211=y")
                enable_config(param, "CONFIG_MAC80211=y")
                enable_config(param, "CONFIG_BRCMSMAC=m")
                enable_config(param, "CONFIG_BRCMFMAC=m")
                enable_config(param, "CONFIG_BRCMFMAC_SDIO=m")
                enable_config(param, "CONFIG_BRCMFMAC_USB=y")
                enable_config(param, "CONFIG_CFG80211_WEXT=y")
            if coverlay == "hack_drm_mxfsb":
                disable_config(param, "CONFIG_DRM_MXSFB")
                disable_config(param, "CONFIG_DRM_IMX")
            for overlay in targets["configoverlays"]:
                if overlay["name"] == coverlay:
                    for oconfig in overlay["list"]:
                        if "disable" in oconfig:
                            disable_config(param, oconfig["config"])
                        else:
                            enable_config(param, oconfig["config"])

    if "configs" in param["target"]:
        for tconfig in param["target"]["configs"]:
            if "disable" in tconfig:
                disable_config(param, tconfig["name"])
            else:
                enable_config(param, tconfig["name"])

    #subprocess.check_output("sed -i 's,^\(CONFIG_SERIAL.*=\)m,\\1y,' %s/.config" % param["kdir"], shell = True)

    if args.debug:
        print("DEBUG: do olddefconfig")
    pbuild = subprocess.run("make %s olddefconfig >/dev/null" % make_opts, shell=True)
    subprocess.check_output("sed -i 's,^.*\(CONFIG_SERIAL.*CONSOLE\).*,\\1=y,' %s/.config" % param["kdir"], shell=True)
    if args.debug:
        print("DEBUG: do olddefconfig")
    pbuild = subprocess.run("make %s olddefconfig >/dev/null" % make_opts, shell=True)
    if args.debug:
        subprocess.Popen("diff -u %s/.config.old %s/.config" % (param["kdir"], param["kdir"]), shell=True)
        print("DEBUG: genconfig end")
    return err

###############################################################################
###############################################################################
def common(sourcename, targetname):
    sourcedir = None
    target = None
    param = {}
    for t_target in targets["targets"]:
        if t_target["name"] == targetname:
            target = t_target
            larch = target["larch"]
            if "flavour" in target:
                flavour = target["flavour"]
            else:
                flavour = "default"
            if "subarch" in target:
                subarch = target["subarch"]
            else:
                subarch = "default"
            break
    if target is None:
        print("ERROR: target %s not found" % targetname)
        sys.exit(1)

    param["toolchaininuse"] = target["toolchaininuse"]

    for t_source in sources["sources"]:
        if t_source["name"] == sourcename:
            sourcedir = os.path.expandvars(t_source["directory"])
            break

    if sourcedir is None or not os.path.exists(sourcedir):
        print("ERROR: source %s not found" % sourcedir)
        sys.exit(1)
    os.chdir(sourcedir)

    kdir = "%s/%s/%s/%s/%s" % (builddir, sourcename, larch, subarch, flavour)
    if args.debug:
        print("DEBUG: Builddir is %s" % kdir)

    if not os.path.isdir(builddir):
        print("DEBUG: %s not exists" % builddir)
        os.mkdir(builddir)
    if not os.path.isdir("%s/header" % builddir):
        print("DEBUG: %s/header not exists" % builddir)
        os.mkdir("%s/header" % builddir)
    headers_dir = "%s/header/%s" % (builddir, targetname)
    if not os.path.isdir(headers_dir):
        print("DEBUG: %s not exists" % headers_dir)
        os.mkdir(headers_dir)
    #else:
        #print("DEBUG: %s exists" % headers_dir)

    make_opts = "ARCH=%s" % larch
    if "cross_compile" in target:
        if target["cross_compile"] == "None":
            print("DEBUG: native compilation")
        else:
            make_opts = make_opts + " CROSS_COMPILE=%s" % target["cross_compile"]
    #else:
    #    print("ERROR: missing cross_compile")
    #    sys.exit(1)

    make_opts = make_opts + " -j%d" % os.cpu_count()
    if "warnings" in target:
        make_opts = make_opts + " " + target["warnings"]
    make_opts = make_opts + " KBUILD_OUTPUT=%s INSTALL_HDR_PATH=%s" % (kdir, headers_dir)
    if "full_tgt" not in target:
        print("ERROR: Missing full_tgt")
        sys.exit(1)

    param["full_tgt"] = target["full_tgt"]
    param["make_opts"] = make_opts
    param["larch"] = larch
    param["subarch"] = subarch
    param["flavour"] = flavour
    param["kdir"] = kdir
    param["targetname"] = targetname
    param["target"] = target
    param["sourcename"] = sourcename
    param["configbase"] = 'generic'

    if "randconfig" in target:
        param["configbase"] = 'randconfig'
        err = genconfig(sourcedir, param, "randconfig")
        if err:
            param["error"] = 1
            return param

    if "defconfig" in target and not args.hc:
        param["configbase"] = target["defconfig"]
        err = genconfig(sourcedir, param, target["defconfig"])
        if err:
            param["error"] = 1
            return param
    if not os.path.exists("%s/.config" % kdir):
            print("No config in %s, cannot do anything" % kdir)
            param["error"] = 1
            return param

    # add modules_install if CONFIG_MODULES
    kconfig = open("%s/.config" % kdir)
    kconfigs = kconfig.read()
    kconfig.close()
    if re.search("CONFIG_MODULES=y", kconfigs):
        modules_dir = "%s/modules/" % builddir
        if not os.path.isdir(modules_dir):
            print("DEBUG: %s not exists" % modules_dir)
            os.mkdir(modules_dir)
        modules_dir = "%s/modules/%s" % (builddir, targetname)
        make_opts = make_opts + " INSTALL_MOD_PATH=%s" % modules_dir
        param["modules_dir"] = modules_dir
        param["make_opts"] = make_opts
    else:
        print("WARNING: no MODULES")
    return param

###############################################################################
###############################################################################
def do_action(sourcename, targetname, action):
    if action == "clean":
        print("CLEAN: %s" % targetname)
        p = common(sourcename, targetname)
        if "error" in p:
            return p["error"]
        linux_clean(p)
        return 0
    if action == "menu":
        print("MENU: %s" % targetname)
        p = common(sourcename, targetname)
        if "error" in p:
            return p["error"]
        linuxmenu(p)
        return 0
    if action == "build":
        print("BUILD: %s" % targetname)
        p = common(sourcename, targetname)
        if "error" in p:
            return p["error"]
        build(p)
        return 0
    if action == "boot":
        p = common(sourcename, targetname)
        if "error" in p:
            return p["error"]
        boot(p)
        return 0
    if action == "qemu":
        p = common(sourcename, targetname)
        if "error" in p:
            return p["error"]
        p["doqemu"] = True
        return boot(p)
    if action == "update":
        do_source_update(sourcename)
        return 0
    if action == "create":
        do_source_create(sourcename)
        return 0
    print("ERROR: unknow action %s" % action)
    return 1

###############################################################################
###############################################################################
def do_source_create(sourcename):
    sourcedir = None

    for t_source in sources["sources"]:
        if t_source["name"] == sourcename:
            sourcedir = os.path.expandvars(t_source["directory"])
            break

    if sourcedir is None:
        print("ERROR: sourcedir is mandatory")
        return 1
    if os.path.exists(sourcedir):
        print("ERROR: source %s already exists at %s" % (sourcename, sourcedir))
        return 1
    if "create_script" in t_source:
        git_create_args = "--sourcedir %s" % sourcedir
        if "ltag" in t_source and t_source["ltag"] is not None:
            git_create_args += " --ltag %s" % t_source["ltag"]
        git_create_cmd = "%s %s" % (t_source["create_script"], git_create_args)
        if args.debug:
            print("DEBUG: Will do %s" % git_create_cmd)
        ret = subprocess.run(git_create_cmd, shell=True)
        return ret.returncode
    if "gituri" not in t_source or t_source["gituri"] is None:
        print("ERROR: Need gituri for %s" % sourcename)
        return 1

    git_opts = ""
    if "branch" in t_source:
        git_opts = "-b %s" % t_source["branch"]
    git_create_cmd = "git clone %s %s %s" % (git_opts, t_source["gituri"], sourcedir)
    if args.noact:
        print("DEBUG: will do %s" % git_create_cmd)
    else:
        ret = subprocess.run(git_create_cmd, shell=True)
        if ret.returncode != 0:
            return ret.returncode

    return 0
###############################################################################
###############################################################################
def do_source_update(sourcename):
    sourcedir = None

    for t_source in sources["sources"]:
        if t_source["name"] == sourcename:
            sourcedir = os.path.expandvars(t_source["directory"])
            break

    if sourcedir is None or not os.path.exists(sourcedir):
        print("ERROR: source %s not found" % sourcedir)
        return 1
    if "update_script" in t_source and t_source["update_script"] is not None:
        print("DEBUG: update with %s" % t_source["update_script"])
        git_update_args = "--sourcedir %s" % sourcedir
        if "ltag" in t_source and t_source["ltag"] is not None:
            git_update_args += " --ltag %s" % t_source["ltag"]

        git_update_cmd = "%s %s" % (t_source["update_script"], git_update_args)
        if args.noact:
            print("INFO: Will do %s" % git_update_cmd)
        else:
            ret = subprocess.run(git_update_cmd, shell=True)
            return ret.returncode
        return 0

###############################################################################
###############################################################################
# validate that the toolchain for targetname works
def toolchain_validate(targetname):
    target = None
    for t_target in targets["targets"]:
        if t_target["name"] == targetname:
            target = t_target
            larch = t_target["larch"]
            break
    if target is None:
        print("ERROR: Cannot found target")
        return 1

    need64bits = False
    if "bits" in target and target["bits"] == 64:
        need64bits = True
        if args.debug:
            print("DEBUG: target need 64 bits")

    #detect native build
    local_arch = platform.machine()
    if local_arch == target["larch"] or (local_arch == 'x86_64' and target["larch"] == 'x86'):
        if args.debug:
            print("DEBUG: no need of cross compiler")
        target["toolchaininuse"] = "Native"
        return 0

    if args.debug:
        print("DEBUG: Try to detect a toolchain")
    toolchain_dir = os.path.expandvars(tc["config"]["toolchains"])
    for toolchain in yto["toolchains"]:
        if toolchain["larch"] != larch:
            if args.debug:
                print("DEBUG: ignore %s due to larch %s" % (toolchain["name"], toolchain["larch"]))
            continue
        if need64bits:
            if "bits" not in toolchain:
                if args.debug:
                    print("DEBUG: ignore %s due to missing bits" % toolchain["name"])
                continue
            if 64 not in toolchain["bits"]:
                if args.debug:
                    print("DEBUG: ignore %s due to missing 64" % toolchain["name"])
                continue
        if args.debug:
            print("DEBUG: Check %s" % toolchain["name"])
        if "path" in toolchain:
            toolchain_realdir = os.path.expandvars(toolchain["path"])
            if args.debug:
                print("DEBUG: add %s to PATH" % toolchain_realdir)
            os.environ["PATH"] = "%s/bin:%s" % (toolchain_realdir, basepath)
        if "url" in toolchain:
            toolchain_file = os.path.basename(toolchain["url"])
            toolchain_subdir = toolchain_file.split(".tar")[0]
            os.environ["PATH"] = "%s/%s/bin:%s" % (toolchain_dir, toolchain_subdir, basepath)
        if "prefix" in toolchain:
            ret = subprocess.run("%sgcc --version >/dev/null 2>/dev/null" % toolchain["prefix"], shell=True)
            if ret.returncode == 0:
                print("INFO: Will use %s as toolchain" % toolchain["name"])
                target["cross_compile"] = toolchain["prefix"]
                target["toolchaininuse"] = toolchain["name"]
                return 0
    return 1

###############################################################################
###############################################################################
def toolchain_download(targetname):
    target = None
    for t_target in targets["targets"]:
        if t_target["name"] == targetname:
            larch = t_target["larch"]
            target = t_target
            break
    if target is None:
        print("ERROR: Cannot found target")
        return 1
    need64bits = False
    if "bits" in target and target["bits"] == 64:
        need64bits = True
        if args.debug:
            print("DEBUG: target need 64 bits")

    print("DEBUG: try to download a toolchain for %s" % larch)
    for toolchain in yto["toolchains"]:
        if toolchain["larch"] != larch:
            continue
        if need64bits:
            if "bits" not in toolchain:
                if args.debug:
                    print("DEBUG: ignore %s due to missing bits" % toolchain["name"])
                continue
            if 64 not in toolchain["bits"]:
                if args.debug:
                    print("DEBUG: ignore %s due to missing 64" % toolchain["name"])
                continue
        if "url" not in toolchain:
            print("Cannot download, missing url")
            continue
        if args.debug:
            print("DEBUG: download from %s" % toolchain["url"])
        subprocess.run("cd %s && wget -N %s" % (cachedir, toolchain["url"]), shell=True)
        #TODO
        toolchain_file = os.path.basename(toolchain["url"])
        tarcmd = "tar xjf"
        if re.search(".xz", toolchain_file):
            tarcmd = "tar xJf"
        if re.search(".gz", toolchain_file):
            tarcmd = "tar xzf"
        toolchain_dir = os.path.expandvars(tc["config"]["toolchains"])
        if not os.path.isdir(toolchain_dir):
            os.mkdir(toolchain_dir)
        toolchain_subdir = toolchain_file.split(".tar")[0]
        subprocess.run("cd %s && %s %s/%s" % (toolchain_dir, tarcmd, cachedir, toolchain_file), shell=True)
        # fix bootlin toolchain TODO HACK
        subprocess.run("cd %s && find %s -iname bison -type f | xargs --no-run-if-empty rm" % (toolchain_dir, toolchain_dir), shell = True)
        if "url" in toolchain:
            toolchain_file = os.path.basename(toolchain["url"])
            toolchain_subdir = toolchain_file.split(".tar")[0]
            os.environ["PATH"] = "%s/%s/bin:%s" % (toolchain_dir, toolchain_subdir, basepath)
        if "prefix" in toolchain:
            ret = subprocess.run("%sgcc --version > /dev/null" % toolchain["prefix"], shell=True)
            if ret.returncode == 0:
                target["cross_compile"] = toolchain["prefix"]
                return 0
    return 1

###############################################################################
###############################################################################
def find_arch_in_kernel(kernelpath):
    # TODO use `file` also
    try:
        p_arch = subprocess.check_output("strings %s |grep -E 'x86-64|x86|armv7'" % kernelpath, shell=True)
    except subprocess.CalledProcessError:
        return None
    for output in p_arch.decode("UTF-8").split("\n"):
        if output == "x86-64":
            return "x86_64"
    return None
###############################################################################
###############################################################################
def bootdir():
    larch = None
    image = None
    iskbuilddir = False
    if os.path.exists("%s/arch" % args.scandir):
        print("INFO: detect a KBUILDIR")
        iskbuilddir = True

    if args.arch is not None:
        larch = args.arch

    if image is None:
        # scan for know kernel
        images = subprocess.check_output("find %s -iname zImage -o -iname Image -o -iname uImage -o -iname bzImage" % args.scandir, shell=True)
        for image in images.decode("UTF-8").split("\n"):
            print(image)
            baseimage = os.path.basename(image)
            if baseimage == "zImage":
                if larch is None:
                    larch = find_arch_in_kernel(image)
                break
            if baseimage == "Image":
                if larch is None:
                    larch = find_arch_in_kernel(image)
                break
            if baseimage == "uImage":
                if larch is None:
                    larch = find_arch_in_kernel(image)
                break
            if baseimage == "bzImage":
                if larch is None:
                    larch = find_arch_in_kernel(image)
                break
            if baseimage == "":
                image = None

    if image is None:
        print("ERROR: Cannot found kernel")
        return 1
    else:
        print("INFO: Found kernel %s" % image)

    if iskbuilddir and larch is None:
        print("DEBUG: detect arch from image path")
        parts = image.split("/")
        goodpart = False
        for part in parts:
            if goodpart:
                larch = part
                break
            if part == "arch":
                goodpart = True

    if larch is None:
        print("ERROR: Cannot detect arch")
        return 1

    p = {}
    p["larch"] = larch
    p["subarch"] = "manual"
    p["flavour"] = "manual"
    p["sourcename"] = "manual"
    p["configbase"] = "manual"
    p["toolchaininuse"] = "unknown"
    p["kdir"] = args.scandir
    os.chdir(args.scandir)
    return boot(p)

###############################################################################
###############################################################################
def do_actions(all_sources, all_targets, all_actions):
    if all_actions == "bootdir":
        if args.scandir is None:
            print("ERROR: --scandir is mandatory")
            sys.exit(1)
        return bootdir()
    #print("DEBUG: Check sources %s with target %s and action %s" % (all_sources, all_targets, all_actions))
    if re.search(",", all_actions):
        for action in all_actions.split(","):
            do_actions(all_sources, all_targets, action)
        return 0
    # all_actions is now only one name
    if all_sources == "all":
        for t_source in sources["sources"]:
            do_actions(t_source["name"], all_targets, all_actions)
        return 0
    if re.search(",", all_sources):
        for sourcearg in all_sources.split(","):
            do_actions(sourcearg, all_targets, all_actions)
        return 0
    # all_sources is now only one name
    if all_actions == "update" or all_actions == "create":
        # no need to cycle target for sources actions
        ret = do_action(all_sources, all_targets, all_actions)
        return ret
    if all_targets is None:
        print("ERROR: target is mandatory")
        return 1
    if all_targets == "all" or all_targets == "defconfig":
        for t_target in targets["targets"]:
            if all_targets == "defconfig" and "defconfig" not in t_target:
                continue
            useit = False
            if args.ttag:
                if args.debug:
                    print("DEBUG: Select target by tags")
                for tag in args.ttag.split(","):
                    if tag == t_target["larch"]:
                        useit = True
                    if tag == t_target["devicetype"]:
                        useit = True
            else:
                useit = True
            if useit:
                do_actions(all_sources, t_target["name"], all_actions)
            else:
                print("DEBUG: ignored due to missing tag")
        return 0
    if re.search(",", all_targets):
        for targetarg in all_targets.split(","):
            do_actions(all_sources, targetarg, all_actions)
        return 0
    # all_targets is now only one name
    Found_target = False
    for ft_target in targets["targets"]:
        if ft_target["name"] == all_targets:
            Found_target = True
            break
    if not Found_target:
        print("ERROR: Cannot found target %s" % all_targets)
        return 1

    # validate toolchain against target
    ret = toolchain_validate(all_targets)
    if ret != 0:
        if all_actions == "download":
            ret = toolchain_download(all_targets)
            return ret
        else:
            print("ERROR: no valid toolchain found for %s" % all_targets)
            return ret
    else:
        if all_actions == "download":
            return ret

    ret = do_action(all_sources, all_targets, all_actions)
    return ret

###############################################################################
###############################################################################

arch = None
outputdir = "/tmp/joboutput/"
boots = {}
builds = {}
templatedir = os.getcwd()
startdir = os.getcwd()
qemu_boot_id = 0
sources_yaml = "sources.yaml"
targets_yaml = "targets.yaml"
dtemplates_yaml = "all.yaml"
config_yaml = "config.yaml"
labs_yaml = "labs.yaml"

os.nice(19)
# ionice need root priv
#subprocess.run("ionice --class 3 --pid %s" % os.getpid())

os.environ["LC_ALL"] = "C"
os.environ["LC_MESSAGES"] = "C"
os.environ["LANG"] = "C"
basepath = os.environ["PATH"]

parser = argparse.ArgumentParser()
parser.add_argument("--noact", "-n", help="No act", action="store_true")
parser.add_argument("--quiet", "-q", help="Quiet, do not print build log", action="store_true")
parser.add_argument("--devtemplates", type=str, help="Path to device templates file")
parser.add_argument("--source", "-s", type=str, help="source to use separated by comma (or all)")
parser.add_argument("--target", "-t", type=str, help="target to use separated by comma (or all)")
parser.add_argument("--ttag", "-T", type=str, help="Select target via some tags")
parser.add_argument("--dtag", "-D", type=str, help="Select device via some tags")
parser.add_argument("--action", "-a", type=str, help="Comma separated list of actions to do between create, update, build, boot, download, qemu")
parser.add_argument("--testsuite", type=str, help="Comma separated list of testss to do", default = None)
parser.add_argument("--debug", "-d", help="increase debug level", action="store_true")
parser.add_argument("--hc", help="Hack: keep config", action="store_true")
parser.add_argument("--nolog", help="Do not use logfile", action="store_true")
parser.add_argument("--noclean", help="Do not clean before building", action="store_true")
parser.add_argument("--rootfs", help="Select the location of rootfs, (ramdisk, nbd, nfs)", choices=['ramdisk', 'nfs', 'nbd'], type=str, default="ramdisk")
parser.add_argument("--configoverlay", "-o", type=str, help="Add config overlay")
parser.add_argument("--randconfigseed", type=str, help="randconfig seed")
parser.add_argument("--scandir", type=str, help="Directory to boot via bootdir action")
parser.add_argument("--arch", type=str, help="Arch to boot via bootdir action", default=None)
parser.add_argument("--waitforjobsend", "-W", help="Wait until all jobs ended", action="store_true")
args = parser.parse_args()

if args.source is None and args.action != "bootdir":
    parser.print_help()
    sys.exit(0)

try:
    tcfile = open(config_yaml)
except IOError:
    print("ERROR: Cannot open bbci config file: %s" % config_yaml)
    sys.exit(1)
tc = yaml.safe_load(tcfile)
if "config" not in tc:
    print("ERROR: invalid config file in %s" % config_yaml)
    sys.exit(1)

if "sources" in tc["config"]:
    sources_yaml = tc["config"]["sources"]
if "devicetemplates" in tc["config"]:
    dtemplates_yaml = tc["config"]["devicetemplates"]
if "targets" in tc["config"]:
    targets_yaml = tc["config"]["targets"]
if "labs" in tc["config"]:
    labs_yaml = tc["config"]["labs"]
if args.debug:
    print("DEBUG: will use labs from %s" % labs_yaml)

if args.devtemplates is not None:
    dtemplates_yaml = args.devtemplates

try:
    tfile = open(dtemplates_yaml)
except IOError:
    print("ERROR: Cannot open device template config file: %s" % dtemplates_yaml)
    sys.exit(1)
t = yaml.safe_load(tfile)

try:
    sources_file = open(sources_yaml)
except IOError:
    print("ERROR: Cannot open sources config file: %s" % sources_yaml)
    sys.exit(1)
sources = yaml.safe_load(sources_file)

try:
    targets_file = open(targets_yaml)
except IOError:
    print("ERROR: Cannot open targets config file: %s" % targets_yaml)
    sys.exit(1)
targets = yaml.safe_load(targets_file)

try:
    tlabsfile = open(labs_yaml)
except IOError:
    print("ERROR: Cannot open labs config file: %s" % labs_yaml)
    sys.exit(1)
tlabs = yaml.safe_load(tlabsfile)

builddir = os.path.expandvars(tc["config"]["builddir"])
cachedir = os.path.expandvars(tc["config"]["cache"])
if not os.path.isdir(cachedir):
    os.mkdir(cachedir)

toolchainfile = open("toolchains.yaml")
yto = yaml.safe_load(toolchainfile)

do_actions(args.source, args.target, args.action)

os.chdir(startdir)
pprint.pprint(builds)
with open('result-build.yml', 'w') as rfile:
    yaml.dump(builds, rfile, default_flow_style=False)
pprint.pprint(boots)
if args.waitforjobsend:
    all_jobs_ended = False
    while not all_jobs_ended:
        time.sleep(10)
        all_jobs_ended = True
        for labname in boots:
            for lab in tlabs["labs"]:
                if lab["name"] == labname:
                    break;
            #print("DEBUG: Check %s with %s" % (labname, lab["lavauri"]))
            server = xmlrpc.client.ServerProxy(lab["lavauri"], allow_none=True)
            for jobid in boots[labname]:
                jobd = server.scheduler.jobs.show(jobid)
                if jobd["state"] != 'Finished':
                    all_jobs_ended = False
                    print("Wait for job %d" % jobid)
                    print(jobd)
                else:
                    boots[labname][jobid]["health"] = jobd["health"]
                    boots[labname][jobid]["state"] = jobd["state"]
with open('result-boots.yml', 'w') as rfile:
    yaml.dump(boots, rfile, default_flow_style=False)

sys.exit(0)
