#!/usr/bin/env python3

import yaml
import os
import subprocess
import argparse

gentoo_source_dir = "/usr/src/gentoo/"
cachedir = "%s/cache/" % os.getcwd()

os.environ["LC_ALL"] = "C"
os.environ["LC_MESSAGES"] = "C"
os.environ["LANG"] = "C"

parser = argparse.ArgumentParser()
parser.add_argument("--ltag", type=str, help="Select device via some tags")
parser.add_argument("--sourcedir", type=str, help="where to store sources")
args = parser.parse_args()


if not os.path.isdir(cachedir):
    os.mkdir(cachedir)
if not os.path.isdir("%s/linux-patches" % cachedir):
    print("DEBUG: checkout gentoo/linux-patches")
    subprocess.check_output("git clone https://github.com/gentoo/linux-patches.git %s/linux-patches" % cachedir, shell=True)
else:
    subprocess.check_output("cd %s/linux-patches && git pull" % cachedir, shell=True)

if args.sourcedir is None:
    print("DEBUG: no sourcedir argument")
    if not os.path.isdir(gentoo_source_dir):
        os.mkdir(gentoo_source_dir)
    finaldir = None
else:
    finaldir = args.sourcedir
    print("DEBUG: will handle %s" % finaldir)

tags = subprocess.check_output("cd %s/linux-patches && git branch -a | grep /[0-9] | sort -V | tail -n2 |sed 's,..*/,,'" % cachedir, shell=True)
for tag in tags.decode("UTF-8").split('\n'):
    if tag == "":
        continue
    if args.ltag is not None and args.ltag != tag:
        continue
    print("Handle %s" % tag)
    try:
        subprocess.check_output("cd %s && wget -N https://cdn.kernel.org/pub/linux/kernel/v4.x/linux-%s.tar.xz" % (cachedir, tag), shell = True)
    except:
        continue
    sourcename = "gentoo-%s" % tag
    subprocess.check_output("cd %s/linux-patches && git checkout %s" % (cachedir, tag), shell = True)
    git_lastcommit = subprocess.check_output('cd %s/linux-patches && git rev-parse HEAD' % cachedir, shell=True).strip().decode("utf-8")
    if finaldir == None:
        finaldir = "%s/linux-%s" % (gentoo_source_dir, tag)
    if os.path.isdir(finaldir):
        floc = open("%s.commit" % finaldir, 'r')
        lastcommit = floc.read()
        floc.close()
        print("Already extracted %s %s" % (git_lastcommit, lastcommit))
        if (lastcommit == git_lastcommit):
            print("no change")
            continue
        subprocess.check_output("rm -r %s" % finaldir, shell = True)
    flc = open("%s.commit" % finaldir, 'w')
    flc.write(git_lastcommit)
    flc.close()
    if not os.path.isdir(finaldir):
        os.mkdir(finaldir)
    subprocess.check_output("tar xJf %s/linux-%s.tar.xz -C %s/.." % (cachedir, tag, finaldir), shell = True)
    subprocess.check_output("cd %s/linux-patches && git checkout %s" % (cachedir, tag), shell = True)
    print("Apply patches")
    patchs = subprocess.check_output("cd %s && ls %s/linux-patches/*patch" % (finaldir, cachedir), shell = True)
    print(patchs)
    for patch in patchs.decode("UTF-8").split('\n'):
        if patch == "":
            continue
        print("Apply %s\n" % patch)
        subprocess.check_output("cd %s && patch -p1 < %s" % (finaldir, patch), shell = True)
