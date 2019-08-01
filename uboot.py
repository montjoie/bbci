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
    make_opts = param["make_opts"]
    print("BUILD: %s to %s" % (larch, kdir))
    if args.debug:
        print("DEBUG: makeopts=%s" % make_opts)

    if args.noact:
        print("Will run make %s" % make_opts)
        return 0
    os.environ["PATH"] = "/mnt/data/uboot/:%s" % os.environ["PATH"]

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

    if args.configoverlay:
        for coverlay in args.configoverlay.split(","):
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
            if "uarch" in target:
                uarch = target["uarch"]
            else:
                uarch = larch
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

    target_type = "uboot"
    if "type" in target:
        target_type = target["type"]

    # default is uboot
    kdir = "%s/%s/%s/%s" % (builddir, sourcename, larch, targetname)
    make_opts = "ARCH=%s" % uarch
    make_opts = make_opts + " KBUILD_OUTPUT=%s" % kdir

    if target_type == "ATF":
        kdir = "%s/%s/%s/%s" % (builddir, sourcename, larch, target["platform"])
        if "platform" in target:
            make_opts = "PLAT=%s debug=1" % target["platform"]
            make_opts = make_opts + " BUILD_BASE=%s" % kdir
        else:
            sys.exit(1)

    if args.debug:
        print("DEBUG: Builddir is %s" % kdir)

    if not os.path.isdir(builddir):
        print("DEBUG: %s not exists" % builddir)
        os.mkdir(builddir)

    if "atf" in target:
        make_opts = make_opts + " BL31=%s/ATF/arm64/%s/%s/release/bl31.bin" % (builddir, target["atf"], target["atf"])
        # TODO validate builded file to containt BL31

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


    param["make_opts"] = make_opts
    param["larch"] = larch
    param["subarch"] = subarch
    param["flavour"] = flavour
    param["kdir"] = kdir
    param["targetname"] = targetname
    param["target"] = target
    param["sourcename"] = sourcename

    # no need of .config
    if target_type == "ATF":
        return param

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
    if action == "build":
        print("BUILD: %s" % targetname)
        p = common(sourcename, targetname)
        if "error" in p:
            return p["error"]
        build(p)
        return 0
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
parser.add_argument("--nolog", help="Do not log", action="store_true")
parser.add_argument("--configoverlay", "-o", type=str, help="Add config overlay")
parser.add_argument("--randconfigseed", type=str, help="randconfig seed")
parser.add_argument("--waitforjobsend", "-W", help="Wait until all jobs ended", action="store_true")
args = parser.parse_args()

tfile = open("uboot.yaml")
t = yaml.safe_load(tfile)

toolchainfile = open("toolchains.yaml")
yto = yaml.safe_load(toolchainfile)

do_actions(args.source, args.target, args.action)

print(builds)
sys.exit(0)
