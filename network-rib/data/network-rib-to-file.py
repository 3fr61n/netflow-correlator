#!usr/bin/python

from netaddr import valid_ipv4
import os
import socket
import time
import requests
from requests.auth import HTTPBasicAuth
import yaml
import sys
import os
import logging
import logging.handlers
import json
from pprint import pprint

ribs = {}
pnhs = {}
status = {}
peer_hash_ids = {}

#openbmp_rest_address = socket.gethostbyname(os.environ['OPENBMP_REST_ADDR'])
#openbmp_rest_port = os.environ['OPENBMP_REST_PORT']
#openbmp_rest_user = os.environ['OPENBMP_REST_USER']
#openbmp_rest_password = os.environ['OPENBMP_REST_PASSWORD']
#openbmp_rest_auth=HTTPBasicAuth(openbmp_rest_user, openbmp_rest_password)
#openbmp_rest_api_base_url='http://'+openbmp_rest_address+':'+openbmp_rest_port

openbmp_rest_address = 'bmp_db_1'
openbmp_rest_port = '8001'
openbmp_rest_user = "openbmp"
openbmp_rest_password = "CiscoRA"
openbmp_rest_auth=HTTPBasicAuth(openbmp_rest_user, openbmp_rest_password)
openbmp_rest_api_base_url='http://'+openbmp_rest_address+':'+openbmp_rest_port

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    # frozen
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # unfrozen
    BASE_DIR = os.path.dirname(os.path.realpath(__file__))

# For each bgp_peer
   # gel All rib, 
        # populate ribs with prefix + pnh
        # populate pnhs with just pnhs
        # use the maping file to copy/clone clients with related RR
# For each bgp peer on ribs
    # for each pnh on pnhs['bgp-peer'
        # resolve pnh on install
        # if not
        # resolve pnh on igp
        # populate ALL nh on ribs and pnh tables (calculate weitgs or %)

def get_peer_hash_ids():
    # Refresh peer_hash_ids dictionary for latter usage 
    global rest_api_base_url
    global openbmp_rest_auth
    global logger
    global openbmp_rest_auth
    global openbmp_rest_api_base_url
    global peer_hash_ids

    peer_hash_ids = {}

    get_peer_url = openbmp_rest_api_base_url+'/db_rest/v1/peer'
    #http://172.30.121.19:8001/db_rest/v1/peer

    resp = requests.get(get_peer_url, auth=openbmp_rest_auth)
    if resp.status_code != 200:
        logger.error('We got wrong status code (%s) from this rest api request (%s)', resp.status_code,get_peer_lookup_url)
#        statsd_client.incr('netflow.stats,result=empty,action=rest_api_error')
    else:
        get_peer_resp = resp.json()
        if get_peer_resp['v_peers']['size'] == 0:
            logger.error('No bgp peers found')
        else:
            peer_hash_ids.clear() 
            for peer in get_peer_resp['v_peers']['data']:
                try:
                    if peer['isUp'] == 1:
                        if peer['isBMPConnected'] == 1:
                            peer_ip = str(peer['PeerIP'])
                            peer_hash_id = str(peer['peer_hash_id'])
                            peer_hash_ids[peer_ip]=peer_hash_id
                        else:
                            logger.error('BGP BMP for peer %s is down', str(peer['PeerIP']))
                    else:
                        logger.error('BGP peer %s is down', str(peer['PeerIP']))
                except e:
                    pass
                # Need to arise an exception about something is wrong with json content
            logger.info('Found %s bgp peers', len(peer_hash_ids))
    
def get_rib_from_peer(**kwargs):
    global loger
    global peer_hash_ids

    router=kwargs['router']
    peer_hash_id = peer_hash_ids[router]
    router_bgp_rib = {}
    router_bgp_pnhs = {}
    
    get_peer_rib_url = openbmp_rest_api_base_url+'/db_rest/v1/rib/peer/'+peer_hash_id+"?limit=10000"
    # We need to check the 'limit > 1000'
    #http://172.30.121.19:8001/db_rest/v1/rib/peer/cc04276117a9c9016103fe6ced642f4e/lookup/20.0.12.81
    logger.info('Performing rest api request: %s', get_peer_rib_url)
    resp = requests.get(get_peer_rib_url, auth=openbmp_rest_auth)
        
    if resp.status_code != 200:
        logger.error('We got wrong status code (%s) from this rest api request (%s)', resp.status_code,get_peer_lookup_url)
#        statsd_client.incr('netflow.stats,result=empty,action=rest_api_error')
    else:            
        get_peer_lookup_resp = resp.json()
        if not get_peer_lookup_resp:
            logger.warn('No bgp route received from %s, matches with %s', router,ipv4_addr)
#            statsd_client.incr('netflow.stats,result=empty,action=get_rib_from_peer')
        else:
            try:
                if int(get_peer_lookup_resp['v_routes']['size']) == 0:
                    logger.warn('No routes found for %s in %s rib', router,ipv4_dst_addr)
                    statsd_client.incr('netflow.stats,result=no-route,action=get_rib_from_peer')
                else:
                    for bgp_route in get_peer_lookup_resp['v_routes']['data']:
                        if bgp_route['isWithdrawn'] == 'false':                     
                            prefix = str(bgp_route['Prefix'])+'/'+str(bgp_route['PrefixLen'])
                            pnh = str(bgp_route['NH'])
                            logger.info('found route %s from %s with nh %s', prefix,router,pnh)
                            router_bgp_rib[prefix] = { 'pnh': pnh }
                            router_bgp_pnhs[pnh] = 'pending-to-resolve'
            except Exception, e:
                logger.error('This exception arise : %s', e)
#                statsd_client.incr('netflow.stats,result=exception,action=get_rib_from_peer')
                pass        
    return router_bgp_rib, router_bgp_pnhs


def resolve_all_pnh (**kwargs):

    global pnhs
    
    router = kwargs['router']
    logger.info('Start to resolve all pnhs for peer %s',router)
    lsp_install_data = {}
    igp_data = {}

#    # Load json containing lsp-install mapping
    dirpath = BASE_DIR + '/lsp-install/'
    filename = 'lsp_install.json'
    path = os.path.join (dirpath,filename)

    with open(path) as lsp_install_file:
        lsp_install_data = json.load(lsp_install_file)

#    # Load json containing igp mapping
    dirpath = BASE_DIR + '/igp-resolve/'
    filename = 'igp_resolve.json'
    path = os.path.join (dirpath,filename)  
#
    with open(path) as igp_file:
        igp_data = json.load(igp_file)

    logger.info('This are all PNHS to resolve: %s for peer %s', pnhs[router],router)
    for pnh in pnhs[router].keys():
        nhs_tmp = []
        logger.info('Resolving pnh %s on peer %s', pnh, router)
        
        if lsp_install_data[router].has_key(pnh):
            tmp = lsp_install_data[router][pnh]
            for endpoint_tmp in tmp['endpoint']:
                tmp2 = {}
                tmp2['endpoint'] = str(endpoint_tmp)
                tmp2['links'] = 1
                tmp2['resolved-via'] = str(tmp['lsp_name'])
                nhs_tmp.append(tmp2)                         
        else:
            clean_pnh = pnh.split('/')[0]
            if router != clean_pnh:
                tmp = igp_data[router][clean_pnh]
                for endpoint_tmp in tmp[router]['endpoint']:
                    tmp2 = {}
                    tmp2['endpoint'] = str(endpoint_tmp)
                    tmp2['links'] = 1
                    tmp2['resolved-via'] = 'igp'
                    nhs_tmp.append(tmp2)
        pnhs[router][pnh] = nhs_tmp 
    #pprint(pnhs[router])

def export_rib_to_file(**kwargs):
    global ribs
    output_directory = '/var/tmp/'
    ribs_output_file = kwargs['ribs_output_file']
    pnhs_output_file = kwargs['pnhs_output_file']
    with open(output_directory + ribs_output_file, 'w') as yaml_file:
        yaml.dump(ribs, yaml_file, default_flow_style=False)

    with open(output_directory + pnhs_output_file, 'w') as yaml_file:
        yaml.dump(pnhs, yaml_file, default_flow_style=False)
# START

# Discover how many peers do we have and get for each bgp peer the hash id
get_peer_hash_ids()

# Get for each bgp peer al incoming routes, then store the prefix/mask/protocol nexthop
for peer_ip in peer_hash_ids.keys():
    ribs[peer_ip], pnhs[peer_ip] = get_rib_from_peer(router=peer_ip)

for peer_ip in pnhs:
    resolve_all_pnh(router=peer_ip)

export_rib_to_file(ribs_output_file='ribs.yaml',pnhs_output_file='pnhs.yaml')

