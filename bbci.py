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

    logdir = os.path.expandvars(t["config"]["logdir"])
    if not os.path.exists(logdir):
        os.mkdir(logdir)

    if args.nolog:
        logfile = sys.stdout
    else:
        logfile = open("%s/%s.log" % (logdir, param["targetname"]), 'w')

    if args.quiet:
        pbuild = subprocess.Popen("make %s" % make_opts, shell=True, stdout=subprocess.DEVNULL)
    else:
        pbuild = subprocess.Popen("make %s 2>&1" % make_opts, shell=True, stdout=logfile)
    outs, err = pbuild.communicate()
    if not args.nolog:
        logfile.close()

    builds[param["targetname"]] = {}
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

    logdir = os.path.expandvars(t["config"]["logdir"])
    if not os.path.exists(logdir):
        os.mkdir(logdir)

    arch_endian = None
    make_opts = param["make_opts"]

    kconfig = open("%s/.config" % kdir)
    kconfigs = kconfig.read()
    kconfig.close()
    if re.search("CONFIG_CPU_BIG_ENDIAN=y", kconfigs):
        endian = "big"
    else:
        endian = "little"
    if re.search("CONFIG_NIOS2=", kconfigs):
        print("NIOS2")
        arch = "nios2"
        arch_endian = "nios2"
        qarch = "nios2"
    if re.search("CONFIG_XTENSA=", kconfigs):
        print("XTENSA")
        arch = "xtensa"
        arch_endian = "xtensa"
        qarch = "xtensa"
    if re.search("CONFIG_SPARC32=", kconfigs):
        print("SPARC32")
        arch = "sparc"
        arch_endian = "sparc"
        qarch = "sparc"
    if re.search("CONFIG_SPARC64=", kconfigs):
        print("SPARC64")
        arch = "sparc64"
        arch_endian = "sparc64"
        qarch = "sparc64"
    if re.search("CONFIG_ARM=", kconfigs):
        print("ARM")
        arch = "arm"
        arch_endian = "armel"
        qarch = "arm"
    if re.search("CONFIG_ARM64=", kconfigs):
        print("ARM64")
        arch = "arm64"
        arch_endian = "arm64"
        qarch = "arm64"
    if re.search("CONFIG_ARC=", kconfigs):
        print("ARC")
        arch = "arc"
        arch_endian = "arc"
        qarch = None
    if re.search("CONFIG_MIPS=", kconfigs):
        if re.search("CONFIG_64BIT=y", kconfigs):
            print("MIPS64")
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
                print("MIPSBE")
                arch_endian = "mipsbe"
            else:
                print("MIPSEL")
                arch_endian = 'mipsel'
                qarch = "mipsel"
    if re.search("CONFIG_ALPHA=", kconfigs):
        print("ARCH: ALPHA")
        arch = "alpha"
        arch_endian = "alpha"
        qarch = "alpha"
    if re.search("CONFIG_PPC=", kconfigs):
        print("ARCH: PPC")
        arch = "powerpc"
        arch_endian = "powerpc"
        qarch = "ppc"
    if re.search("CONFIG_PPC64=", kconfigs):
        print("ARCH: PPC64")
        arch = "powerpc64"
        arch_endian = "ppc64"
        qarch = "ppc64"
    if re.search("CONFIG_OPENRISC=", kconfigs):
        print("ARCH: OPENRISC")
        arch = "openrisc"
        arch_endian = "openrisc"
        qarch = "or1k"
    if re.search("CONFIG_MICROBLAZE=", kconfigs):
        print("ARCH: MICROBLAZE")
        arch = "microblaze"
        if re.search("CONFIG_CPU_BIG_ENDIAN=y", kconfigs):
            arch_endian = "microblaze"
            qarch = "microblaze"
        else:
            arch_endian = "microblazeel"
            qarch = "microblazeel"
    if re.search("CONFIG_X86_64=", kconfigs):
        print("X86_64")
        arch = "x86_64"
        arch_endian = "x86_64"
        qarch = "x86_64"
    if re.search("CONFIG_X86=", kconfigs) and not re.search("CONFIG_X86_64=", kconfigs):
        print("X86")
        arch = "x86"
        arch_endian = "x86"
        qarch = "i386"

    if arch_endian is None:
        print("ERROR: Missing endian arch")
        return 1

    # TODO check RAMFS and INITRD and MODULES and DEVTMPFS_MOUNT

    #TODO check error
    if os.path.isdir(".git"):
        git_describe = subprocess.check_output('git describe', shell=True).strip().decode("utf-8")
        git_lastcommit = subprocess.check_output('git rev-parse HEAD', shell=True).strip().decode("utf-8")
    else:
        VERSION = subprocess.check_output('grep ^VERSION Makefile | sed "s,.* ,,"', shell=True).strip().decode("utf-8")
        PATCHLEVEL = subprocess.check_output('grep ^PATCHLEVEL Makefile | sed "s,.* ,,"', shell=True).strip().decode("utf-8")
        SUBLEVEL = subprocess.check_output('grep ^SUBLEVEL Makefile | sed "s,.* ,,"', shell=True).strip().decode("utf-8")
        EXTRAVERSION = subprocess.check_output('grep ^EXTRAVERSION Makefile | sed "s,.* ,,"', shell=True).strip().decode("utf-8")
        git_describe = "%s.%s.%s%s" % (VERSION, PATCHLEVEL, SUBLEVEL, EXTRAVERSION)
        git_lastcommit = "None"

    # generate modules.tar.gz
    #TODO check error
    if "modules_dir" in param:
        modules_dir = param["modules_dir"]
    else:
        modules_dir = "%s/fake" % builddir
        os.mkdir(modules_dir)
        os.mkdir("%s/lib/" % modules_dir)
        os.mkdir("%s/lib/modules" % modules_dir)
    if args.quiet:
        pbuild = subprocess.Popen("cd %s && tar czf modules.tar.gz lib" % modules_dir, shell=True, stdout=subprocess.DEVNULL)
        outs, err = pbuild.communicate()
    else:
        pbuild = subprocess.Popen("cd %s && tar czf modules.tar.gz lib" % modules_dir, shell=True)
        outs, err = pbuild.communicate()

    for device in t["templates"]:
        if "devicename" in device:
            devicename = device["devicename"]
        else:
            devicename = device["devicetype"]
        print("==============================================")
        print("CHECK: %s" % devicename)
        if "larch" in device:
            device_larch = device["larch"]
        else:
            device_larch = device["arch"]
        if device_larch != larch:
            print("\tSKIP: larch")
            continue
        if device["arch"] != arch:
            print("\tSKIP: arch: %s vs %s" % (device["arch"], arch))
            continue
        # check config requirements
        skip = False
        if "configs" in device and device["configs"] is not None:
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
        if "qemu" in device:
            jobf = open("%s/defaultqemu.yaml" % templatedir)
        else:
            jobf = open("%s/default.yaml" % templatedir)
        jobt = jobf.read()
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
        jobt = jobt.replace("__KERNELFILE__", kernelfile)
        jobt = jobt.replace("__DEVICETYPE__", device["devicetype"])
        jobt = jobt.replace("__MACH__", device["mach"])
        jobt = jobt.replace("__ARCH__", device["arch"])
        jobt = jobt.replace("__PATH__", "%s/%s/%s/%s" % (sourcename, larch, subarch, flavour))
        jobt = jobt.replace("__ARCHENDIAN__", arch_endian)
        jobt = jobt.replace("__GIT_DESCRIBE__", git_describe)
        jobt = jobt.replace("__KVERSION__", git_describe)
        jobt = jobt.replace("__KENDIAN__", endian)
        jobt = jobt.replace("__KERNELTYPE__", kerneltype)
        jobt = jobt.replace("__GIT_LASTCOMMIT__", git_lastcommit)
        jobt = jobt.replace("__JOBNAME__", "AUTOTEST %s %s/%s/%s/%s on %s" % (git_describe, sourcename, larch, subarch, flavour, devicename))
        # now convert to YAML
        ft = yaml.load(jobt)
        for dtag in device["tags"]:
            if dtag == "notests":
                if args.debug:
                    print("DEBUG: Remove test from job")
                newaction = []
                for action in ft["actions"]:
                    if "test" not in action:
                        newaction.append(action)
                ft["actions"] = newaction
        if "dtb" in device:
            for action in ft["actions"]:
                if "deploy" in action:
                    if "qemu" in device:
                        action["deploy"]["images"]["dtb"] = {}
                        action["deploy"]["images"]["dtb"]["url"] = "__BOOT_FQDN__/%s/%s/%s/%s/dts/%s" % (sourcename, larch, subarch, flavour, device["dtb"])
                    else:
                        action["deploy"]["dtb"] = {}
                        action["deploy"]["dtb"]["url"] = "__BOOT_FQDN__/%s/%s/%s/%s/dts/%s" % (sourcename, larch, subarch, flavour, device["dtb"])
        if "qemu" in device:
            print("\tQEMU")
            ft["context"] = {}
            ft["context"]["arch"] = qarch
            if "netdevice" in device["qemu"]:
                ft["context"]["netdevice"] = "tap"
            if "model" in device["qemu"]:
                ft["context"]["model"] = device["qemu"]["model"]
            if "machine" in device["qemu"]:
                ft["context"]["machine"] = device["qemu"]["machine"]
            if "cpu" in device["qemu"]:
                ft["context"]["cpu"] = device["qemu"]["cpu"]
            if "memory" in device["qemu"]:
                ft["context"]["memory"] = device["qemu"]["memory"]
            if "guestfs_interface" in device["qemu"]:
                ft["context"]["guestfs_interface"] = device["qemu"]["guestfs_interface"]
            if "guestfs_driveid" in device["qemu"]:
                ft["context"]["guestfs_driveid"] = device["qemu"]["guestfs_driveid"]
            if "extra_options" in device["qemu"]:
                ft["context"]["extra_options"] = device["qemu"]["extra_options"]
            for action in ft["actions"]:
    #            if "boot" in action:
    #                action["boot"]["method"] = "qemu"
    #                action["boot"]["media"] = "tmpfs"
                if "deploy" in action:
    #                action["deploy"]["to"] = "tmpfs"
    #                action["deploy"]["kernel"]["image_arg"] = '-kernel {dtb}'
    #                action["deploy"]["ramdisk"]["image_arg"] = '-initrd {dtb}'
                    if "dtb" in device:
                        action["deploy"]["images"]["dtb"]["image_arg"] = '-dtb {dtb}'
    #    else:
    #        for action in ft["actions"]:
    #            if "boot" in action:
    #                action["boot"]["commands"] = "ramdisk"
        cachedir = os.path.expandvars(t["config"]["cache"])
        fw = open("%s/job-%s.yaml" % (cachedir, devicename), "w")
        yaml.dump(ft, fw, default_flow_style=False)
        fw.close()
        jobf.close()
        if "doqemu" in param:
            if "qemu" not in device:
                return 0
            failure = None
            qemu_cmd = "qemu-system-%s -kernel %s -nographic -machine %s" % (qarch, kfile, device["qemu"]["machine"])
            if "extra_options" in device["qemu"]:
                for extrao in device["qemu"]["extra_options"]:
                    # TODO hack
                    if re.search("lavatest", extrao):
                        continue
                    qemu_cmd += " %s" % extrao
            if re.search("CONFIG_SERIAL_PMACZILOG=", kconfigs) and re.search("CONFIG_SERIAL_PMACZILOG_TTYS=y", kconfigs):
                print("INFO: PMACZILOG console hack")
                qemu_cmd = qemu_cmd.replace("console=ttyPZ0", "console=ttyS0")
            #qemu_cmd += " -drive format=qcow2,file=$HOME/bbci/flash.bin"
            if "dtb" in device:
                dtbfile = "%s/arch/%s/boot/dts/%s" % (kdir, larch, device["dtb"])
                if not os.path.isfile(dtbfile):
                    print("SKIP: no dtb at %s" % dtbfile)
                    continue
                qemu_cmd += " -dtb %s" % dtbfile
            if "memory" in device["qemu"]:
                qemu_cmd += " -m %s" % device["qemu"]["memory"]
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

            qlogfile = open("%s/%s.log" % (logdir, device["name"].replace('/', '_')), 'w')
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
                dtbfile = "%s/arch/%s/boot/dts/%s" % (kdir, larch, device["dtb"])
                dtbsubdir = device["dtb"].split('/')
                dtb_relpath = "/dts/"
                if len(dtbsubdir) > 1:
                    dtb_relpath = dtb_relpath + dtbsubdir[0]
                if not os.path.isfile(dtbfile):
                    print("SKIP: no dtb at %s" % dtbfile)
                    continue
                lab_copy(lab, dtbfile, "%s/%s" % (data_relpath, dtb_relpath))
            # modules.tar.gz
            lab_copy(lab, "%s/modules.tar.gz" % modules_dir, data_relpath)
            # final job
            if not os.path.isdir(outputdir):
                os.mkdir(outputdir)
            if not os.path.isdir("%s/%s" % (outputdir, lab["name"])):
                os.mkdir("%s/%s" % (outputdir, lab["name"]))
            result = subprocess.check_output("chmod -R o+rX %s" % datadir, shell=True)
            #print(result.decode("UTF-8"))
            jobf = open("%s/job-%s.yaml" % (cachedir, devicename))
            jobt = jobf.read()
            jobf.close()
            jobt = jobt.replace("__BOOT_FQDN__", lab["datahost_baseuri"])
            jobt = jobt.replace("__ROOT_FQDN__", lab["rootfs_baseuri"])
            jobf = open("%s/%s/job-%s.yaml" % (outputdir, lab["name"], devicename), 'w')
            # HACK CONFIG_SERIAL_PMACZILOG=y CONFIG_SERIAL_PMACZILOG_TTYS=y
            if re.search("CONFIG_SERIAL_PMACZILOG=", kconfigs) and re.search("CONFIG_SERIAL_PMACZILOG_TTYS=y", kconfigs):
                print("INFO: PMACZILOG console hack")
                jobt = jobt.replace("console=ttyPZ0", "console=ttyS0")
            jobf.write(jobt)
            jobf.close()
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
    pbuild = subprocess.Popen("make %s %s >/dev/null" % (make_opts, defconfig), shell=True)
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
            if coverlay == "cpu_be":
                enable_config(param, "CONFIG_CPU_BIG_ENDIAN=y")
            if coverlay == "cpu_el":
                disable_config(param, "CONFIG_CPU_BIG_ENDIAN=y")
            if coverlay == "hack_drm_mxfsb":
                disable_config(param, "CONFIG_DRM_MXSFB")
                disable_config(param, "CONFIG_DRM_IMX")
            for overlay in t["configoverlays"]:
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
    for t_target in t["targets"]:
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

    for t_source in t["sources"]:
        if t_source["name"] == sourcename:
            sourcedir = os.path.expandvars(t_source["directory"])
            break

    if sourcedir is None or not os.path.exists(sourcedir):
        print("ERROR: source %s not found" % sourcedir)
        sys.exit(1)
    os.chdir(sourcedir)

    builddir = os.path.expandvars(t["config"]["builddir"])

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

    if "randconfig" in target:
        err = genconfig(sourcedir, param, "randconfig")
        if err:
            param["error"] = 1
    if not os.path.exists("%s/.config" % kdir) or "defconfig" in target:
        if "defconfig" in target:
            err = genconfig(sourcedir, param, target["defconfig"])
            if err:
                param["error"] = 1
                return param
        else:
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
        if os.path.isdir(modules_dir):
            print("DEBUG: clean old %s" % modules_dir)
            shutil.rmtree(modules_dir)
        os.mkdir(modules_dir)
        if args.debug:
            print("DEBUG: add modules_install")
        param["full_tgt"] = "%s modules_install" % (param["full_tgt"])
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
    for t_source in t["sources"]:
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
        subprocess.run(git_create_cmd, shell=True)
        return 0
    if "gituri" not in t_source or t_source["gituri"] is None:
        print("ERROR: Need gituri for %s" % sourcename)
        return 1

    git_create_cmd = "git clone %s %s" % (t_source["gituri"], sourcedir)
    if args.noact:
        print("DEBUG: will do %s" % git_create_cmd)
    else:
        subprocess.run(git_create_cmd, shell=True)
    #TODO check return
###############################################################################
###############################################################################
def do_source_update(sourcename):
    for t_source in t["sources"]:
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
            subprocess.run(git_update_cmd, shell=True)
        return 0

###############################################################################
###############################################################################
# validate that the toolchain for targetname works
def toolchain_validate(targetname):
    target = None
    for t_target in t["targets"]:
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
    if "cross_compile" in target:
        if target["cross_compile"] == "None":
            if args.debug:
                print("DEBUG: no need for cross_compile")
            return 0
        ret = subprocess.run("%sgcc --version > /dev/null" % target["cross_compile"], shell=True)
        if ret.returncode == 0:
            if args.debug:
                print("DEBUG: cross_compile prefix is valid")
            return 0
        print("ERROR: Current cross_compile settings is wrong")

    #detect native build
    local_arch = platform.machine()
    if local_arch == target["larch"]:
        print("DEBUG: no need of cross compiler")
        return 0

    if args.debug:
        print("DEBUG: Try to detect a toolchain")
    toolchain_dir = os.path.expandvars(t["config"]["toolchains"])
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
            ret = subprocess.run("%sgcc --version >/dev/null" % toolchain["prefix"], shell=True)
            if ret.returncode == 0:
                print("INFO: Will use %s as toolchain" % toolchain["name"])
                target["cross_compile"] = toolchain["prefix"]
                return 0
    return 1

###############################################################################
###############################################################################
def toolchain_download(targetname):
    target = None
    for t_target in t["targets"]:
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
    cachedir = os.path.expandvars(t["config"]["cache"])
    if not os.path.isdir(cachedir):
        os.mkdir(cachedir)
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
        toolchain_dir = os.path.expandvars(t["config"]["toolchains"])
        if not os.path.isdir(toolchain_dir):
            os.mkdir(toolchain_dir)
        toolchain_subdir = toolchain_file.split(".tar")[0]
        subprocess.run("cd %s && %s %s/%s" % (toolchain_dir, tarcmd, cachedir, toolchain_file), shell=True)
        # fix bootlin toolchain TODO HACK
        subprocess.run("cd %s && find %s -iname bison -type f | xargs rm" % (toolchain_dir, toolchain_dir))
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
def do_actions(all_sources, all_targets, all_actions):
    #print("DEBUG: Check sources %s with target %s" % (all_sources, all_targets))
    if re.search(",", all_actions):
        for action in all_actions.split(","):
            do_actions(all_sources, all_targets, action)
        return 0
    # all_actions is now only one name
    if all_sources == "all":
        for t_source in t["sources"]:
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
        for t_target in t["targets"]:
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
    for ft_target in t["targets"]:
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
qemu_boot_id = 0

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
parser.add_argument("--source", "-s", type=str, help="source to use separated by comma (or all)")
parser.add_argument("--target", "-t", type=str, help="target to use separated by comma (or all)")
parser.add_argument("--ttag", "-T", type=str, help="Select target via some tags")
parser.add_argument("--dtag", "-D", type=str, help="Select device via some tags")
parser.add_argument("--action", "-a", type=str, help="one of create,update,build,boot")
parser.add_argument("--debug", "-d", help="increase debug level", action="store_true")
parser.add_argument("--nolog", help="Do not use logfile", action="store_true")
parser.add_argument("--configoverlay", "-o", type=str, help="Add config overlay")
parser.add_argument("--randconfigseed", type=str, help="randconfig seed")
parser.add_argument("--waitforjobsend", "-W", help="Wait until all jobs ended", action="store_true")
args = parser.parse_args()

tfile = open("all.yaml")
t = yaml.load(tfile)
tlabsfile = open("labs.yaml")
tlabs = yaml.load(tlabsfile)

toolchainfile = open("toolchains.yaml")
yto = yaml.load(toolchainfile)

do_actions(args.source, args.target, args.action)

print(builds)
print(boots)
if args.waitforjobsend:
    for labname in boots:
        for job in boots[labname]:
            print(job)
sys.exit(0)
