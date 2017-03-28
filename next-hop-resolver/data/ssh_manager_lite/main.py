from ssh_manager_lite import ssh_manager_lite
import re
import pytricia
import argparse 
import pprint 
import sys
import os
import time
import logging
import logging.handlers
from flask import Flask

def return_data(target,bgp_nh):

   
   rib = {}
   
   connector = ssh_manager_lite (target=target)
   device = connector.open()

   mpls_conf =  connector.command_executor(device,'show configuration protocols mpls | display set')
   loopback_config = connector.command_executor(device,'show configuration interface lo0.0 | display set')
   
   connector.close(device)
   
   ################### CISCO REGEX #############################

   #cisco_lsp_name = "(?:signalled-name)(\s+.*)"
   #regex_cisco_lsp_name = re.search(cisco_lsp_name, cisco_config,re.MULTILINE)
   #cisco_lsp = regex_cisco_lsp_name.group(1).strip()

   #cisco_install = "(?:autoroute)(?: destination)(.*)"
   #regex_cisco_install = re.search(cisco_install, cisco_config,re.MULTILINE)
   #cisco_install = regex_cisco_install.group(1).strip()

   #cisco_endpoint = "(?:tunnel-te[0-9]+)(?: destination)(.*)"
   #regex_cisco_endpoint  = re.search(cisco_endpoint, cisco_config,re.MULTILINE)
   #cisco_endpoint = regex_cisco_endpoint.group(1).strip()

   ################### JNPR REGEX #############################

   regex_install  = "(?:install)(\s+\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{2})"
   match_install = re.search(regex_install, mpls_conf,re.MULTILINE)
   install = match_install.group(1).strip()

   regex_endpoint = "(?:to)(\s+\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
   match_endpoint = re.findall(regex_endpoint, mpls_conf,re.MULTILINE)

   regex_lsp_name = "(?:label-switched-path).(.*?\s+)"
   match_lsp_name = re.search(regex_lsp_name, mpls_conf,re.MULTILINE)
   lsp_name = match_lsp_name.group(1).strip()

   regex_lo0 = "(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{2})(\s+primary)"
   match_lo0 = re.search(regex_lo0, loopback_config,re.MULTILINE)
   lo0 = match_lo0.group(1).strip()

   rib[target] = pytricia.PyTricia()
   rib[target][bgp_nh] = {'install':install,'endpoint':match_endpoint,'lsp_name':lsp_name}
   
   return rib[target][bgp_nh]

################################################################################################
# Create and Parse Arguments
################################################################################################

if getattr(sys, 'frozen', False):
    # frozen
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # unfrozen
    BASE_DIR = os.path.dirname(os.path.realpath(__file__))

full_parser = argparse.ArgumentParser()

full_parser.add_argument("--target", default=None, help="Host")
full_parser.add_argument("--bgp_nh", default=None, help="BGP NH")

dynamic_args = vars(full_parser.parse_args())

target = dynamic_args['target']
bgp_nh = dynamic_args['bgp_nh']

# Need to validata input data

if not(dynamic_args['target']):
   print "Error, target is mandatory"
   sys.exit(0)





if __name__ == "__main__":

  return_data(target,bgp_nh)

