#!flask/bin/python
from flask import Flask, jsonify
import pytricia
from netaddr import valid_ipv4
import os
import socket
import time
import requests
from requests.auth import HTTPBasicAuth
from pprint import pprint
import logging
import logging.handlers
import sys
import yaml
import copy

app = Flask(__name__)

ribs = {}
pnhs = {}
status = {}
peer_hash_ids = {}
bgp_rib_mapping = {}

recursion_depth_max = 15

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


BASE_DIR_INPUT = '/var/tmp/'
RIBS_FILENAME = 'ribs-efrain.yaml'
PNHS_FILENAME = 'pnhs.yaml'

#ribs['router_id']['prefix'] = { 'pnh': ip_address, 'nhs': { nh1: 3, nh2: 2, nh3: 1 }  # pueden haber varios caminos al mismo PE

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

# Rest API should
    #  Update ribs
    #  Status ( ready to be pooled, updating rib, error updating rib)
    #  Recursive lockup  (input router, destination), return a { exit_router: weight,  exit_router2: weight2}


@app.route('/network-rib/api/v1.0/status')
def status():
#   It would be nice to ask the rest api about what is he doing, however if we
# are single thread/single core, I thing it would be as useful as I would like to be
    global status
    data = {}
    #peer_hash_ids = get_peer_hash_ids()
    data['result'] = status
    return jsonify(data)



@app.route('/network-rib/api/v1.0/update_ribs/',methods=['GET'])
def update_rib():
    global ribs
    ribs_tmp = {}
    ribs_yaml = {}
    ribs_yaml_file = BASE_DIR_INPUT + RIBS_FILENAME
    with open(ribs_yaml_file) as f:
        try:
            ribs_yaml = yaml.load(f)
        except Exception, e:
            logger.error('Error importing ribs file: %s', ribs_yaml_file)
            logging.exception(e)
            sys.exit(0)        

    # transform ribs_tmp on ribs  (based on pytricia)
    
    for peer in ribs_yaml.keys():
        ribs_tmp[peer] = pytricia.PyTricia()
        for prefix, pnhs in ribs_yaml[peer].items():
            ribs_tmp[peer][prefix] = pnhs
            logger.info('Adding entry on peer %s for prefix %s with pnh %s', peer, prefix, pnhs) 



    ribs = copy.deepcopy(ribs_tmp)
    # delete temporal files
    ribs_tmp.clear()
    ribs_yaml.clear()
    data = {}
    data['result'] = 'Successful ribs load from ' + str(len(ribs)) + ' peers'
    return jsonify(data)
    

@app.route('/network-rib/api/v1.0/update_pnhs/',methods=['GET'])
def update_pnhs():
    global pnhs
    pnhs_tmp = {}
    pnhs_yaml = {}
    pnhs_yaml_file = BASE_DIR_INPUT + PNHS_FILENAME
    with open(pnhs_yaml_file) as f:
        try:
            pnhs_yaml = yaml.load(f)
        except Exception, e:
            logger.error('Error importing pnhs file: %s', pnhs_yaml_file)
            logging.exception(e)
            sys.exit(0)        

    #NOTE:  there is no need for pytricia because all PNHs are /32

    pnhs = copy.deepcopy(pnhs_tmp)
    # delete temporal files
    pnhs_tmp.clear()
    pnhs_yaml.clear()
    data = {}
    data['result'] = 'Successful pnhs load from ' + str(len(pnhs)) + ' peers'
    return jsonify(data)


#@app.route('/network-rib/api/v1.0/update_pnhs/',methods=['GET'])
#def analyze_path(**kwargs):
#    global logger
#    source_router=kwargs['source_router']
#    ipv4_dst_addr=kwargs['ipv4_dst_addr']
#    intermediate_router=kwargs['intermediate_router']
#    bytes_sent=kwargs['bytes_sent']
#    packets_sent=kwargs['packets_sent']
#    recursion_depth=kwargs['recursion_depth']
#
#    bgp_routes = []
#    bgp_routes = bgp_ipv4_lookup(router=intermediate_router, ipv4_addr=ipv4_dst_addr)
#   
#    ############
#    #NOTE:  bgp_routes is a list of bgp_route with the following content    
#    #bgp_route['NH'] 
#    #bgp_route['AS_Path']
#    #bgp_route['PeerAddress'] 
#    #bgp_route['Prefix'] 
#    #bgp_route['PrefixLen']   
#    ############
#    if bgp_routes:   # Need to confirm if this really match a non-empty dict
#        for bgp_route in bgp_routes:
#            bytes_sent_per_route = bytes_sent / len(bgp_routes)
#            packets_sent_per_route = packets_sent / len(bgp_routes)
#
#            if recursion_depth > recursion_depth_max:
#                # Recursion depth is too high, we should STOP and notify, about a possible loop or a very long path
#                tags='src_PE='+str(source_router)+', dst_PE='+str(intermediate_router)+',recursion='+str(recursion_depth)
#                statsd_client.incr('netflow.real.bytes,'+tags,count=bytes_sent_per_route)
#                statsd_client.incr('netflow.real.packets,'+tags,count=packets_sent_per_route)
#            elif bgp_route['NH'] == intermediate_router:
#                # update the practical matrix with source_router|intermediate_router|bytes_per_bgp_nh|packets_per_bgp_nh               
#                tags='src_PE='+str(source_router)+', dst_PE='+str(intermediate_router)+',recursion='+str(recursion_depth)
#                statsd_client.incr('netflow.real.bytes,'+tags,count=bytes_sent_per_route)
#                statsd_client.incr('netflow.real.packets,'+tags,count=packets_sent_per_route)
#
#                # there is a special case if the fist-hop is the final-host
#                if intermediate_router == source_router:   # first hop analysis
#                    # update the theorical matrix with source_router|bgp_nh|bytes_per_bgp_nh|packets_per_bgp_nh
#                    tags='src_PE='+str(source_router)+', dst_PE='+str(intermediate_router)+',recursion='+str(recursion_depth)
#                    statsd_client.incr('netflow.theorical.bytes,'+tags,count=bytes_sent_per_route)
#                    statsd_client.incr('netflow.theorical.packets,'+tags,count=packets_sent_per_route)
#            else:
#                if intermediate_router == source_router:  # first hop analysis
#                    # update the theorical matrix with source_router|bgp_nh|bytes_per_bgp_nh|packets_per_bgp_nh
#                    tags='src_PE='+str(source_router)+', dst_PE='+str(bgp_route['NH'])+',recursion='+str(recursion_depth)
#                    statsd_client.incr('netflow.theorical.bytes,'+tags,count=bytes_sent_per_route)
#                    statsd_client.incr('netflow.theorical.packets,'+tags,count=packets_sent_per_route)
#                
#                next_hops = resolve_bgp_nexthop(router=intermediate_router,ipv4_addr=bgp_route['NH'])
#                # Look for possible install routes to lsp
#                
#                bytes_sent_per_next_hop = bytes_sent_per_route / len(next_hops)
#                packets_sent_per_next_hop = packets_sent_per_route / len(next_hops)
#
#                for next_hop in next_hops:
#                    logger.info('my nexthop to recurse %s', next_hop)
#                    link_name = next_hop['link_name']  # this is the link or neighbor
#                    endpoint = next_hop['endpoint']
#                    # update per-LSP matrix with lsp_name
#                    tags='src_PE=' + str(source_router) + ', ' \
#                         'dst_PE=' + str(bgp_route['NH']) + ', ' \
#                         'recursion=' + str(recursion_depth) + ', ' \
#                         'link_name=' + str(link_name) + ', ' \
#                         'endpoint_A=' + str(intermediate_router) + ', ' \
#                         'endpoint_B=' + str(endpoint) + ', ' \
#                         'recursion=' + str(recursion_depth)
#                    statsd_client.incr('netflow.link_stats.bytes,'+tags,count=bytes_sent_per_route)
#                    statsd_client.incr('netflow.link_stats.packets,'+tags,count=packets_sent_per_route)
#                    recursion_depth = recursion_depth + 1
#                    analyze_path(source_router=source_router,ipv4_dst_addr=ipv4_dst_addr,intermediate_router=endpoint,bytes_sent=bytes_sent_per_next_hop,packets_sent=packets_sent_per_next_hop,recursion_depth=recursion_depth)
#
#    else:
#        logger.error('No bgp route found from %s, to %s', source_router,ipv4_dst_addr)




#@app.route('/network-rib/api/v1.0/update-rib',methods=['GET'])
#def update_rib():
##  This api call, will update a temporary data structure and at the end it will
##  replace the real data structure of ribs and pnhs
#
#    global ribs
#    global pnhs
#    global status
#    global peer_hash_ids
#    ribs_tmp = {}
#    phnh_tmp = {}
#
## The logic should be like
## Get all peers (and hash_ids)
## For each bgp_peer
#   # gel All rib, 
#        # populate ribs with prefix + pnh    ribs_tmp['peer_id']['prefix']['pnh'] = 'ip_address'
#        # populate pnhs with just pnhs       pnhs_tmp['peer_id']['pnh'] = [ list with related prefixes with weight ]
#        # use the maping file to copy/clone clients with related RR
## For each peer_id on ribs_tmp
#    # for each pnh on pnhs[peer_id]
#        # resolve pnh on install (checking router config)
#        # if not resolve
#        #   resolve pnh on igp
#        # populate ALL nh on ribs_tmp (you have the related prefixes on pnhs_tmp['peer_id']['pnh']) (calculate weitgs or %)
#
#    peer_hash_ids = {}
#    peer_hash_ids = get_peer_hash_ids()
#
#    for peer_ip in peer_hash_ids.keys():
#        ribs_tmp[peer_ip], pnhs_tmp[peer_ip] = get_rib_from_peer(peer_ip=peer_ip)
##  host file structure
#    # router1:   related RR
#    # router2:   related RR
#    #load yaml file
#    for router in router_to_bgp_rr_mapping:
#        if not ribs_tmp.has_key[router]:
#            ribs_tmp[router] = ribs_tmp[router_to_bgp_rr_mapping[router]]
#            pnhs_tmp[router] = pnhs_tmp[router_to_bgp_rr_mapping[router]]
#    for router in pnhs_tmp:
#        for pnh in pnhs_tmp[router]:
#            nhs = resolve_pnh(router=router,pnh=pnh)    # nhs = [ { nh1x3, nh2x2}]
#
#
#
#
#    for peer_ip in 
#    for 
#
#    if bgp_rib_to_router_mapping.has_key(router)
#        logger.info('Performing rest api request: %s', get_peer_lookup_url)
#    router = bgp_rib_to_router_mapping[router]
#
#
#
#
#
#    data = { 'result' : bgp_peer_ribs[str(bgp_peer)][str(prefix)] }
#
#    return jsonify(data)
#
#@app.route('/network-rib/api/v1.0/analyze_path/<peer_id>/<prefix>',methods=['GET'])
#def analyze_path_tmp(peer_id,prefix):
# 
#    # Validate router/prefix are valid IP addresss and that we have a entry on ribs for peer_id
#    initial_weight = 1
#    source_router = peer_id
#    ipv4_dst_addr = prefix
#    nhs = ribs_tmp['peer_id']['prefix']['nhs']
#        # calculate frantions of weithg / len(nhs)
#        for nh in nhs:
#            if nh == peer_id
#                #insert data on database with path
#
#
#        analyze_path(source_router=source_router,ipv4_dst_addr=ipv4_dst_addr,intermediate_router=endpoint,bytes_sent=bytes_sent_per_next_hop,packets_sent=packets_sent_per_next_hop,recursion_depth=recursion_depth)
#
#    # First attempt
#    # Check nh 
#    # if nh = peer_id


if __name__ == '__main__':
    app.run(debug=True)