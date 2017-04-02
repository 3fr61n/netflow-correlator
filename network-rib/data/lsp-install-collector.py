# Catch Paramiko warnings about libgmp and RandomPool
import warnings
with warnings.catch_warnings(record=True) as w:
    import paramiko

import multiprocessing
from datetime import datetime
import re
import netmiko
from netmiko.ssh_exception import NetMikoTimeoutException, NetMikoAuthenticationException
import pytricia
import pprint
import os 
import sys
import json
# DEVICE_CREDS contains the devices to connect to
from DEVICE_CREDS import all_devices


def worker_commands(a_device, mp_queue):
  
    try:
        a_device['port']
    except KeyError:
        a_device['port'] = 22

    identifier = '{ip}'.format(**a_device)
    return_data = {}
    cmd = ''
    command_jnpr = 'show configuration protocols mpls | display set'
    command_csco = 'show  running-config  formal interface | i tunnel'
    
    SSHClass = netmiko.ssh_dispatcher(a_device['device_type'])
    try:
        net_connect = SSHClass(**a_device)
        if net_connect.device_type == 'juniper':
            cmd = net_connect.send_command(command_jnpr)
        elif net_connect.device_type == 'cisco_ios':
            cmd = net_connect.send_command(command_csco)
    except (NetMikoTimeoutException, NetMikoAuthenticationException) as e:
        return_data[identifier] = False

        # Add data to the queue (for parent process)
        mp_queue.put(return_data)
        return None
    #print cmd
    return_data[identifier] = pytricia.PyTricia()
    return_data[identifier] = generate_json(cmd,identifier,net_connect.device_type)
    mp_queue.put(return_data)


def generate_json(cmd,ip_host,device_type):
   
   rib = {} 
   

   install = None
   lsp_name = None
   
   if device_type == 'juniper':
    
    ################### JNPR REGEX #############################
    regex_install  = "(?:install)(\s+\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{2})"
    match_install = re.search(regex_install, cmd,re.MULTILINE)
    if match_install:
        install = match_install.group(1).strip().split('/')[0]

    regex_endpoint = "(?:to)(\s+\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    match_endpoint = re.findall(regex_endpoint, cmd,re.MULTILINE)

    regex_lsp_name = "(?:label-switched-path).(.*?\s+)"
    match_lsp_name = re.search(regex_lsp_name, cmd,re.MULTILINE)
    if match_lsp_name:
        lsp_name = match_lsp_name.group(1).strip()

   else:

   ################### CISCO REGEX #############################

    cisco_lsp_name = "(?:signalled-name)(\s+.*)"
    regex_cisco_lsp_name = re.search(cisco_lsp_name, cmd,re.MULTILINE)
    if regex_cisco_lsp_name:
        lsp_name = regex_cisco_lsp_name.group(1).strip()

    cisco_install = "(?:autoroute)(?: destination)(.*)"
    regex_cisco_install = re.search(cisco_install, cmd,re.MULTILINE)
    if regex_cisco_install:
        install = regex_cisco_install.group(1).strip()

    cisco_endpoint = "(?:tunnel-te[0-9]+)(?: destination)(.*)"
    match_endpoint  = re.findall(cisco_endpoint, cmd,re.MULTILINE)
    #match_endpoint = regex_cisco_endpoint.group(1).strip()


   rib[install] = {'install':install,'endpoint':match_endpoint,'lsp_name':lsp_name}
   
   return rib


def main():

    if getattr(sys, 'frozen', False):
        # frozen
        BASE_DIR = os.path.dirname(sys.executable)
    else:
        # unfrozen
        BASE_DIR = os.path.dirname(os.path.realpath(__file__))

    dirpath = BASE_DIR + '/lsp-install/'
    filename = 'lsp_install.json'
            
    # Create directory if does not exist
    if not os.path.exists (dirpath):
        os.makedirs (dirpath,mode=0777)

    install = {}
    path = os.path.join (dirpath,filename)  
    results = []
    mp_queue = multiprocessing.Queue()
    processes = []

    for a_device in all_devices:
        p = multiprocessing.Process(target=worker_commands, args=(a_device, mp_queue))
        processes.append(p)
        # start the work process
        p.start()
    # wait until the child processes have completed
    for p in processes:
        p.join()
    # retrieve all the data from the queue
    for p in processes:
        results.append(mp_queue.get())
    for i in results:
        install.update(i)   
    with open (path,'w') as outfile:        
        json.dump(install,outfile)
    
if __name__ == '__main__':

    main()




