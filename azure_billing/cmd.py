#!/opt/app-root/bin/python3

import argparse
import sys
import yaml

from . import billing
from . import db


def processArgs():
  parser = argparse.ArgumentParser(description='Ansible Automation Platform Azure billing connector', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  group = parser.add_mutually_exclusive_group()
  group.add_argument('-it', action='store_true', dest='doinstalltrigger', help='Install unique host trigger and process billing')
  group.add_argument('-rt', action='store_true', dest='doremovetrigger', help='Remove unique host trigger and stop')
  return parser.parse_args()

def loadConfig():
  with open("config.yaml") as cfgfile:
    cfg = yaml.safe_load(cfgfile)
  return cfg

args = processArgs()
cfg = loadConfig()

# Connect to DB
db.login(cfg['db']['name'],
         cfg['db']['user'],
         cfg['db']['pass'],
         cfg['db']['host'],
         cfg['db']['port'])


# Add or remove trigger if requested
if args.doinstalltrigger:
  db.installHostHistoryTrigger()
  print("Trigger installed.")
elif args.doremovetrigger:
  db.removeHostHistoryTrigger()
  print("Trigger removed.")
  sys.exit(0)


# Do billing for unbilled hosts
hosts = db.getNewHosts()


if hosts:
  billing.pegBillingCounter('someplan', 'hosts', len(hosts))

# Mark hosts as billed if successful
db.markHostsBilled(hosts)
