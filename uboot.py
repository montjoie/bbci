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
import logging

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
parser.add_argument("--nolog", help="Do not log", action="store_true")
parser.add_argument("--configoverlay", "-o", type=str, help="Add config overlay")
parser.add_argument("--tvendor", type=str, help="Choose specific toolchain vendor")
parser.add_argument("--randconfigseed", type=str, help="randconfig seed")
parser.add_argument("--waitforjobsend", "-W", help="Wait until all jobs ended", action="store_true")
args = parser.parse_args()

tfile = open("uboot.yaml")
t = yaml.safe_load(tfile)

toolchainfile = open("toolchains.yaml")
yto = yaml.safe_load(toolchainfile)

class bbci:
    def __init__(self):
        print("init BBCI")
        logging.basicConfig()
        self.logger = logging.getLogger("bbci")
        self.ldebug = False
        if args.debug:
            self.logger.setLevel(logging.DEBUG)
            self.ldebug = True
        self.dologs = True
        self.doclean = True

        tfile = open("uboot.yaml")
        self.cfg = yaml.safe_load(tfile)
        self.builddir = os.path.expandvars(self.cfg["config"]["builddir"])

        self.logdir = os.path.expandvars(t["config"]["logdir"])
        if not os.path.exists(self.logdir):
            os.mkdir(self.logdir)

        toolchainfile = open("toolchains.yaml")
        self.toolchains = yaml.safe_load(toolchainfile)

        self.basepath = os.environ["PATH"]
        self.logger.info("INIT DONE")

    def disable_config(self, param, dconfig):
        subprocess.run("cp %s/.config %s/.config.old" % (param["kdir"], param["kdir"]), shell=True)
        with open("%s/.config" % param["kdir"], 'r') as fconfig:
            wconfig = fconfig.read()
        if not re.search("%s=" % dconfig, wconfig):
            print("DEBUG: %s is already disabled" % dconfig)
            return 0
        wconfig = re.sub("%s.*" % dconfig, "# %s is not set" % dconfig, wconfig)
        with open("%s/.config" % param["kdir"], 'w') as fconfig:
            fconfig.write(wconfig)
        make_opts = param["make_opts"]
        pbuild = subprocess.run("make %s olddefconfig" % make_opts, shell=True)
        if self.ldebug:
            subprocess.run("diff -u %s/.config.old %s/.config" % (param["kdir"], param["kdir"]), shell=True)
        # verify it is still disabled
        with open("%s/.config" % param["kdir"], 'r') as fconfig:
            wconfig = fconfig.read()
            if re.search("^%s=" % dconfig, wconfig):
                print("BADDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD")
        return pbuild.returncode

    def enable_config(self, param, econfig):
        rawconfig = econfig.split("=")[0]

        self.logger.debug("DEBUG: Try enable config %s" % econfig)
        subprocess.run("cp %s/.config %s/.config.old" % (param["kdir"], param["kdir"]), shell=True)
        with open("%s/.config" % param["kdir"], 'r') as fconfig:
            wconfig = fconfig.read()
        if re.search("=", econfig):
            if re.search("%s" % econfig, wconfig):
                self.logger.debug("DEBUG: %s is already enabled" % econfig)
                return 0
            wconfig = re.sub("# %s is not set" % rawconfig, "%s" % econfig, wconfig)
            # handle case CONFIG="" replaced by CONFIG="xxxx"
            wconfig = re.sub("%s=.*" % rawconfig, "%s" % econfig, wconfig)
        else:
            if re.search("%s=" % econfig, wconfig):
                self.logger.debug("DEBUG: %s is already enabled" % econfig)
                return 0
            wconfig = re.sub("# %s is not set" % rawconfig, "%s=y" % econfig, wconfig)
        with open("%s/.config" % param["kdir"], 'w') as fconfig:
            fconfig.write(wconfig)
        make_opts = param["make_opts"]
        pbuild = subprocess.run("make %s olddefconfig > /dev/null" % make_opts, shell=True)
        if self.ldebug:
            subprocess.run("diff -u %s/.config.old %s/.config" % (param["kdir"], param["kdir"]), shell=True)
        return pbuild.returncode

    def toolchain_download(self, url):
        self.logger.debug(f"DEBUG: try to download toolchain {url}")
        cachedir = os.path.expandvars(self.cfg["config"]["cache"])
        if not os.path.isdir(cachedir):
            os.mkdir(cachedir)
        subprocess.run("cd %s && wget -N %s" % (cachedir, url), shell=True)
        #TODO
        toolchain_file = os.path.basename(url)
        tarcmd = "tar xjf"
        if re.search(".xz", toolchain_file):
            tarcmd = "tar xJf"
        toolchain_dir = os.path.expandvars(t["config"]["toolchains"])
        if not os.path.isdir(toolchain_dir):
            os.mkdir(toolchain_dir)
        toolchain_subdir = toolchain_file.split(".tar")[0]
        subprocess.run("cd %s && %s %s/%s" % (toolchain_dir, tarcmd, cachedir, toolchain_file), shell=True)
        # fix bootlin toolchain TODO HACK
        subprocess.run("find %s -iname bison -type f | xargs --no-run-if-empty rm" % (toolchain_dir), shell=True)

    def find_toolchain(self, larch):
        r = {}
        r["prefix"] = None

        local_arch = platform.machine()
        if local_arch == larch:
            self.logger.debug("DEBUG: no need of cross compiler")
            return r

        self.logger.debug(f"DEBUG: Try to detect a toolchain for {larch}")
        toolchain_dir = os.path.expandvars(self.cfg["config"]["toolchains"])
        for toolchain in self.toolchains["toolchains"]:
            if toolchain["larch"] != larch:
                #self.logger.debug("DEBUG: ignore %s due to larch %s" % (toolchain["name"], toolchain["larch"]))
                continue
            if args.tvendor and "vendor" not in toolchain:
                continue
            self.logger.debug("DEBUG: Check toolchain %s" % toolchain["name"])
            if "path" in toolchain:
                toolchain_realdir = os.path.expandvars(toolchain["path"])
                self.logger.debug("DEBUG: add %s to PATH" % toolchain_realdir)
                os.environ["PATH"] = "%s/bin:%s" % (toolchain_realdir, basepath)
                self.logger.debug(f'DEBUG: PATH is {os.environ["PATH"]}')
            if "url" in toolchain:
                url = toolchain["url"]
                toolchain_file = os.path.basename(url)
                toolchain_subdir = toolchain_file.split(".tar")[0]
                toolchaindir = f"{toolchain_dir}/{toolchain_subdir}"
                self.logger.debug(f"DEBUG: toolchain should be in {toolchaindir}")
                if not os.path.isdir(toolchaindir):
                    self.toolchain_download(url)
                os.environ["PATH"] = "%s/%s/bin:%s" % (toolchain_dir, toolchain_subdir, os.environ["PATH"])
                self.logger.debug(f'DEBUG: PATH is {os.environ["PATH"]}')
            if "prefix" in toolchain:
                ret = subprocess.run("%sgcc --version >/dev/null" % toolchain["prefix"], shell=True)
                if ret.returncode == 0:
                    self.logger.info("INFO: Will use %s as toolchain" % toolchain["name"])
                    r["prefix"] = toolchain["prefix"]
                    return r
        return None

    def checkout(self, sourcename):
        scfg = None
        for t_target in t["sources"]:
            if t_target["name"] == sourcename:
                scfg = t_target
                break
        if scfg is None:
            self.logger.error(f"ERROR: checkout: did not found {sourcename}")
            return None
        self.logger.info(f"DEBUG: found source {scfg}")
        sourcedir = os.path.expandvars(scfg["directory"])
        self.logger.debug(f"DEBUG: source directory is {sourcedir}")

        if "gituri" not in scfg:
            self.logger.error(f"ERROR: Need gituri for {sourcename}")
            return None

        if not os.path.exists(sourcedir):
            git_create_cmd = f'git clone {scfg["gituri"]} {sourcedir}'
            if args.noact:
                self.logger.debug("DEBUG: will do %s" % git_create_cmd)
            else:
                subprocess.run(git_create_cmd, shell=True)
        else:
            self.logger.debug("DEBUG: source already checkouted")
            subprocess.run(f"git -C {sourcedir} fetch", shell=True)

        if "branch" in scfg:
            branch = scfg["branch"]
            ret = subprocess.run(f"git -C {sourcedir} checkout {branch}", shell = True)
            if ret.returncode != 0:
                return None

        if "update" in scfg:
            subprocess.run(f"git -C {sourcedir} pull", shell = True)

        self.logger.debug(f"DEBUG: check status of {sourcename}")
        subprocess.run(f"git -C {sourcedir} status", shell=True)

        return sourcedir

    def do_optee(self, target):
        opteename = target["optee"]
        self.logger.info(f"OPTEE: {opteename}")
        optee = None
        for t_target in t["targets"]:
            if "type" not in t_target:
                #self.logger.debug(f"DEBUG: ignore{t_target}")
                continue
            if t_target["type"] != 'optee':
                continue
            if t_target["name"] == opteename:
                optee = t_target
                break
        if optee is None:
            self.logger.error(f"ERROR: OPTEE: fail to find config for {opteename}")
            return 1
        self.logger.info(f"DEBUG: found OPTEE {optee}")
        opteedir = self.checkout("optee")
        if opteedir is None:
            self.logger.error(f"ERROR: fail to checkout {opteename}")
            return 1
        self.logger.info(f"INFO: compile OPTEE")
        larch = optee["larch"]
        kdir = "%s/OPTEE/%s/%s" % (self.builddir, larch, opteename)
        self.opteekdir = kdir
        make_opts = "O=%s" % kdir

        to = self.find_toolchain(larch)
        if to is None:
            self.logger.error("Fail to find a toolchain for {larch}")
            return 1
        if to["prefix"] is None:
            self.logger.debug("DEBUG: native compilation")
        else:
            make_opts += " CROSS_COMPILE64=%s" % to["prefix"]
        to32 = self.find_toolchain("arm")
        if to32 is None:
            self.logger.error("Fail to find a toolchain for {larch}32")
            return 1
        if to32["prefix"] is None:
            self.logger.debug("DEBUG: native compilation for ARM32")
        else:
            make_opts += " CROSS_COMPILE=%s" % to32["prefix"]

        self.logger.debug(f"DEBUG: MAKE {make_opts}")

        # TODO
        make_opts += " CFG_ARM64_core=y"
        if "platform" in optee:
            make_opts += " PLATFORM=%s" % optee["platform"]

        os.chdir(opteedir)
        if self.doclean:
            pbuild = subprocess.run("make %s clean 2>&1" % make_opts, shell=True)
        if args.nolog:
            logfile = sys.stdout
        else:
            logpath = "%s/%s.optee.log" % (self.logdir, target["name"])
            self.logger.debug(f"Logging to {logpath}")
            logfile = open(logpath, 'w')
        pbuild = subprocess.run("make %s 2>&1" % make_opts, shell=True, stdout=logfile)
        return pbuild.returncode

    def do_atf(self, target):
        atfname = target["atf"]
        self.logger.info(f"ATF: {atfname}")
        atf = None
        for t_target in t["targets"]:
            if t_target["name"] == atfname:
                atf = t_target
                break
        if atf is None:
            return 1
        self.logger.info(f"DEBUG: found ATF {atf}")
        if "source" in atf:
            source = atf["source"]
        else:
            source = "ATF"
        atfdir = self.checkout(source)
        if atfdir is None:
            return 1
        self.logger.info(f"INFO: compile ATF")
        larch = atf["larch"]
        kdir = "%s/ATF/%s/%s" % (self.builddir, larch, atfname)
        self.logger.debug(f"Building in {kdir}")
        self.atfkdir = kdir
        make_opts = "BUILD_BASE=%s" % kdir
        if "platform" in atf:
            #make_opts = "PLAT=%s debug=1" % atf["platform"]
            make_opts += " PLAT=%s" % atf["platform"]
            if "makeopts" in atf:
                self.logger.info("ADD make hacks")
                make_opts += " " + atf["makeopts"]

        if larch == "arm64":
            make_opts += " ARCH=aarch64"
        else:
            make_opts += f" ARCH={larch}"

        if "spd" in atf:
            make_opts += f' SPD={atf["spd"]}'
        if "target_board" in atf:
            make_opts += f' TARGET_BOARD={atf["target_board"]}'

        to = self.find_toolchain(larch)
        if to is None:
            self.logger.error("Fail to find a toolchain")
            return 1
        if to["prefix"] is None:
            self.logger.debug("DEBUG: native compilation")
        else:
            make_opts += " CROSS_COMPILE=%s" % to["prefix"]
            if "hack" in atf and atf["hack"] == 'M0_CROSS_COMPILE':
                to32 = self.find_toolchain("arm")
                if to32 is None:
                    self.logger.error("Fail to find a toolchain32")
                    return 1
                make_opts += f' M0_CROSS_COMPILE={to32["prefix"]}'
        self.logger.debug(f"DEBUG: MAKE {make_opts}")

        os.chdir(atfdir)
        if self.doclean:
            pbuild = subprocess.run("make %s clean 2>&1" % make_opts, shell=True)
        pbuild = subprocess.run("make %s 2>&1" % make_opts, shell=True)
        return pbuild.returncode

    def do_crust(self, target):
        crustname = target["crust"]
        self.logger.info(f"CRUST: {crustname}")
        crust = None
        for t_target in t["targets"]:
            if "type" not in t_target:
                continue
            if t_target["type"] != 'crust':
                continue
            if t_target["name"] == crustname:
                crust = t_target
                break
        if crust is None:
            self.logger.error("Fail to find crust config")
            return 1
        self.logger.info(f"DEBUG: found ATF {crust}")
        crustdir = self.checkout("crust")
        self.crustdir = crustdir
        if crustdir is None:
            return 1
        self.logger.info(f"INFO: compile crust")

        to = self.find_toolchain("openrisc")
        if to is None:
            self.logger.error("ERROR: crust: failed to find a toolchain")
            return 1
        kdir = "%s/crust" % (self.builddir)
        make_opts = f'CROSS_COMPILE={to["prefix"]} OBJ={kdir}'
        make_opts = f'CROSS_COMPILE={to["prefix"]}'
        self.logger.debug(f"DEBUG: MAKE {make_opts}")

        defconfig = crust['config']

        os.chdir(crustdir)
        if self.doclean:
            pbuild = subprocess.run("make %s clean 2>&1" % make_opts, shell=True)
        self.logger.info("CRUST: defconfig")
        pbuild = subprocess.run("make %s %s 2>&1" % (make_opts, defconfig), shell=True)
        self.logger.info("CRUST: make")
        pbuild = subprocess.run("make %s 2>&1" % make_opts, shell=True)
        return pbuild.returncode

    def do_uboot(self, sourcename, target):
        if "defconfig" not in target:
            self.logger.error(f"Fail to find defconfig in {target}")
            return 1
        defconfig = target["defconfig"]
        self.logger.info(f"uboot: {defconfig}")
        udir = self.checkout(sourcename)
        if udir is None:
            return 1
        self.logger.info(f"INFO: compile UBOOT")
        larch = target["larch"]
        if "uarch" in target:
            uarch = target["uarch"]
        else:
            uarch = larch
        kdir = "%s/uboot/%s/%s" % (self.builddir, larch, defconfig)
        make_opts = "ARCH=%s" % uarch
        make_opts += " KBUILD_OUTPUT=%s" % kdir
        to = self.find_toolchain(larch)
        if to is None:
            return 1
        if to["prefix"] is None:
            self.logger.debug("DEBUG: native compilation")
        else:
            make_opts += " CROSS_COMPILE=%s" % to["prefix"]
        if "atf" in target:
            #bl31path = "%s/ATF/arm64/%s/%s/release/%s" % (self.builddir, atf, platform, atfbl31)
            # easiest way is to find it
            bl31name = "bl31.bin"
            if "bl31name" in target:
                bl31name = target["bl31name"]
            self.logger.debug(f"DEBUG: seek bl31 {bl31name}")
            # TODO handle debug vs release
            r = subprocess.run(f'find {self.atfkdir} -iname {bl31name} |grep release', shell=True, capture_output=True)
            bl31path = r.stdout.decode("UTF8").rstrip()
            if len(bl31path) == 0:
                self.logger.error(f"FAIL to find {bl31name}")
                return 1
            self.logger.debug(f"BL31 is {bl31path}")
            if bl31path[0] != '/':
                return 1
            make_opts += f" BL31={bl31path}"
        if "optee" in target:
            teename = "tee-raw.bin"
            r = subprocess.run(f"find {self.opteekdir} -iname {teename}", shell=True, capture_output=True)
            teepath = r.stdout.decode("UTF8").rstrip()
            if len(teepath) == 0:
                self.logger.error(f"Fail to find {teename}")
                return 1
            if teepath[0] != '/':
                self.logger.error(f"Fail to find {teename} invalid path {teepath}")
                return 1
            make_opts += f" TEE={teepath}"
        if "crust" in target:
            make_opts += f' SCP={self.crustdir}/build/scp/scp.bin'
        if "rockchip_tpl" in target:
            tplname = target["rockchip_tpl"]
            rkbindir = self.checkout("rkbin")
            self.logger.debug(f"RKBIN is at {rkbindir}")
            self.logger.debug(f"Search TPL {tplname}")
            r = subprocess.run(f"find {rkbindir} -iname {tplname}", shell=True, capture_output=True)
            tplpath = r.stdout.decode("UTF8").rstrip()
            if len(tplpath) == 0:
                self.logger.error("ERROR: didnt found TPL")
                return 1
            self.logger.debug(f"TPL is at {tplpath}")
            make_opts += f" ROCKCHIP_TPL={tplpath}"
        # hack for beagleia64
        if "extra" in target:
            for ename in target["extra"]:
                edir = self.checkout("ti-firmware")
                make_opts += f' {ename}={edir}'
        make_opts += " -j%d" % os.cpu_count()
        self.logger.debug(f"DEBUG: MAKE {make_opts}")
        os.chdir(udir)
        if self.doclean:
            pbuild = subprocess.run("make %s clean 2>&1" % make_opts, shell=True)
        pbuild = subprocess.run("make %s %s 2>&1" % (make_opts, defconfig), shell=True)
        param = {}
        param["kdir"] = kdir
        param["make_opts"] = make_opts
        if "configs" in target:
            for tconfig in target["configs"]:
                if "disable" in tconfig:
                    self.disable_config(param, tconfig["name"])
                else:
                    self.enable_config(param, tconfig["name"])
        if args.nolog:
            logfile = sys.stdout
        else:
            logpath = "%s/%s.log" % (self.logdir, target["name"])
            self.logger.debug(f"Logging to {logpath}")
            logfile = open(logpath, 'w')
        pbuild = subprocess.run("make %s 2>&1" % make_opts, shell=True, stdout=logfile)
        ret = pbuild.returncode
        if ret != 0:
            self.logger.error("BUILD ERROR")
            return ret
        if "uboot_images" in target:
            images = target["uboot_images"]
            for image in images:
                self.logger.info(f"SEEK for {image}")
                if not os.path.exists(f"{kdir}/{image}"):
                    self.logger.error("NOT FOUND")
                    return 1
                else:
                    self.logger.info("FOUND")
            if "ubootstore" not in self.cfg["config"]:
                self.logger.info("No ubootstore, no copy of images")
                return 0
            if "ubootname" not in target:
                self.logger.info("Mising ubootname, no copy of images")
                return 0
            for image in images:
                ubootstore = os.path.expandvars(self.cfg["config"]["ubootstore"])
                r = subprocess.run(f"git -C {udir} describe", shell=True, capture_output=True)
                ubootv = r.stdout.decode("UTF8").rstrip()
                ubootname = target["ubootname"]
                fname = f"{ubootname}-{ubootv}-{image}"
                self.logger.debug(f"Final name is {fname}")
                subprocess.run(f"cp {kdir}/{image} {ubootstore}/{fname}", shell=True)
                subprocess.run(f"chmod 644 {ubootstore}/{fname}", shell=True)
        else:
            self.logger.info("No uboot_images")

    def actions(self, source, targetname, actions):
        self.logger.debug(f"CALLED with {source} {actions}")
        if actions is None:
            self.logger.error("ERROR: no action")
            return 1
        if re.search(",", actions):
            for action in actions.split(","):
                self.action(source, targetname, action)
            return 0
        self.action(source, targetname, actions)

    def action(self, source, targetname, action):
        self.logger.info(f"DEBUG: action start for {action}")
        if targetname == 'all':
            for tgt in t["targets"]:
                self.action(source, tgt["name"], action)
            return 0
        if action == 'update':
            if source == 'all':
                for src in t["sources"]:
                    self.action(src["name"], targetname, action)
                return 0
            self.checkout(source)
            return 0
        self.logger.info(f"DEBUG: seek {targetname}")
        sourcedir = None
        target = None
        param = {}
        for t_target in t["targets"]:
            self.logger.debug(f"CHECK {targetname} in {t_target}")
            if "source" in t_target and t_target["source"] != source:
                continue
            if t_target["name"] == targetname:
                target = t_target
                break
        if target is None:
            self.logger.error("target %s not found" % targetname)
            return 1
        self.logger.debug(f"TARGET is {target}")
        if "atf" in target:
            ret = self.do_atf(target)
            if ret != 0:
                return ret
        if "optee" in target:
            ret = self.do_optee(target)
            if ret != 0:
                return ret
        if "crust" in target:
            ret = self.do_crust(target)
            if ret != 0:
                return ret
        if "type" in target:
            if target["type"] in ["crust", "ATF", "optee"]:
                # TODO ignore for the moment
                return 0
        self.do_uboot(source, target)

bbci = bbci()
bbci.actions(args.source, args.target, args.action)

sys.exit(0)

do_actions(args.source, args.target, args.action)

print(builds)
sys.exit(0)
