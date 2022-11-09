#!/usr/bin/env python3

import datetime
from datetime import timedelta
from datetime import datetime
import os
import time
import re
import xmlrpc.client
import sys
import yaml
import json
import argparse

# retcode 0 = job complete
# 1 = icomplete
# other 2
ret = 2

parser = argparse.ArgumentParser()
parser.add_argument("--lavauri", "-u", type=str, help="LAVA URI", default=None)
parser.add_argument("--jobid", "-j", type=str, help="jobid", default=None)
parser.add_argument("--wait", "-w", action="store_true", help="jobid", default=False)
args = parser.parse_args()

if args.jobid == None:
    print("Need jobid")
    sys.exit(2)

server = xmlrpc.client.ServerProxy(args.lavauri, allow_none=True)

wait = False
if args.wait:
    wait = True

while wait:
    try:
        job_state = server.scheduler.job_details(args.jobid)
        if job_state["status"] == "Complete":
            ret = 0
            wait = False
            print(job_state["status"])
        if job_state["status"] == "Incomplete":
            ret = 1
            wait = False
            print(job_state["status"])
    except xmlrpc.client.Fault:
        print("ERROR: no details")
        sys.exit(2)
    time.sleep(10)

try:
    job_out_raw = server.scheduler.job_output(args.jobid)
    job_out = yaml.unsafe_load(job_out_raw.data)
except xmlrpc.client.Fault:
    print("ERROR: no job output")
    sys.exit(2)

flog = open("%s.log" % args.jobid, 'w')
flogh = open("%s.html" % args.jobid, 'w')
flogh.write('<html><head><link rel="stylesheet" href="/lava/log.css" type="text/css" /></head><body>')
for line in job_out:
                #if "lvl" in line and (line["lvl"] == "info" or line["lvl"] == "debug" or line["lvl"] == "target" or line["lvl"] == "feedback"):
    for msg in line["msg"]:
        flog.write(msg)
        flogh.write(msg)
    flog.write("\n")
    flogh.write("<br>\n")
flogh.write("</body></html>")
flog.close()
flogh.close()

sys.exit(ret)
