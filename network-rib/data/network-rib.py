#!flask/bin/python
from __future__ import division
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
import json

app = Flask(__name__)

ribs = {}
pnhs = {}
status = {}
peer_hash_ids = {}
bgp_rib_mapping = {}

recursion_depth_max = 15

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR_INPUT = '/data/'
RIBS_FILENAME = 'ribs.yaml'
PNHS_FILENAME = 'pnhs.yaml'
BGP_RIB_MAPPING_FILENAME = 'bgp_rib_mapping.yaml'

@app.route('/network-rib/api/v1.0/status')
def status(rest_api=True):
#   It would be nice to ask the rest api about what is he doing, however if we
# are single thread/single core, I thing it would be as useful as I would like to be
    global status
    data = {}
    #peer_hash_ids = get_peer_hash_ids()
    data['result'] = status
    if rest_api:
        return jsonify(data)
    else:
        return json.dumps(data)

@app.route('/network-rib/api/v1.0/update_ribs/',methods=['GET'])
def update_ribs(rest_api=True):
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

    for peer in ribs_yaml.keys():
        logger.debug('Start to populate pytricia object for peer %s', peer) 
        ribs[peer] = pytricia.PyTricia()
        for prefix, pnhs in ribs_yaml[peer].items():
            ribs[peer][prefix] = pnhs
            logger.debug('Adding entry on peer %s for prefix %s with pnh %s', peer, prefix, pnhs) 

    data = {}
    data['result'] = 'Successful ribs load from ' + str(len(ribs)) + ' peers'
    if rest_api:
        return jsonify(data)
    else:
        return json.dumps(data)

@app.route('/network-rib/api/v1.0/update_pnhs/',methods=['GET'])
def update_pnhs(rest_api=True):
    global pnhs

    pnhs_yaml = {}
    pnhs_yaml_file = BASE_DIR_INPUT + PNHS_FILENAME
    with open(pnhs_yaml_file) as f:
        try:
            #pnhs_yaml = yaml.load(f)
            pnhs = yaml.load(f)
        except Exception, e:
            logger.error('Error importing pnhs file: %s', pnhs_yaml_file)
            logging.exception(e)
            sys.exit(0)        

    data = {}
    data['result'] = 'Successful pnhs load from ' + str(len(pnhs)) + ' peers'
    if rest_api:
        return jsonify(data)
    else:
        return json.dumps(data)

@app.route('/network-rib/api/v1.0/update_bgp_mapping/',methods=['GET'])
def update_bgp_mapping(rest_api=True):
    global bgp_rib_mapping

    bgp_rib_mapping_yaml = {}
    bgp_rib_mapping_yaml_file = BASE_DIR_INPUT + BGP_RIB_MAPPING_FILENAME
    with open(bgp_rib_mapping_yaml_file) as f:
        try:
            bgp_rib_mapping = yaml.load(f)
        except Exception, e:
            logger.error('Error importing pnhs file: %s', bgp_rib_mapping_yaml_file)
            logging.exception(e)
            sys.exit(0)        

    data = {}
    data['result'] = 'Successful bgp rib mapping load from ' + str(len(bgp_rib_mapping)) + ' peers'
    if rest_api:
        return jsonify(data)
    else:
        return json.dumps(data)

@app.route('/network-rib/api/v1.0/rib_lookup/<peer_tmp>/<prefix_tmp>',methods=['GET'])
def rib_lookup(peer_tmp,prefix_tmp,rest_api=True):
    # This function will be used to calculate the theorical matrix
    global ribs
    global pnhs
    global bgp_rib_mapping
    peer = str(peer_tmp)   
    prefix = str(prefix_tmp)

    data = {}
    if valid_ipv4(peer):
        #data['result'] = 'Its a valid IP addres %s' % (peer)
        if bgp_rib_mapping.has_key(peer):

            mapped_bgp_rib_peer = bgp_rib_mapping[peer]
            if ribs.has_key(mapped_bgp_rib_peer):
                #data['result'] = 'We have a rib for that peer %s' % (peer)
                if valid_ipv4(prefix):
                    #data['result'] = 'We have valid prefix  %s' % (peer)
                    try:
                        rib_tmp = ribs[mapped_bgp_rib_peer]
                        pnh = rib_tmp[prefix]
                        data['pnh'] = pnh['pnh']
                        data['nhs'] = pnhs[peer][pnh['pnh']]
                    except KeyError, e:
                        data['result'] = 'Prefix %s not found on %s' % (prefix,mapped_bgp_rib_peer)
                    except Exception, e:
                        logging.exception(e)
                        pass 
                else:
                    data['error'] = 'Not a valid IP addres for peer: %s' % (prefix)
            else:
                data['error'] = 'There is no rib related to the mapped bgp peer: %s' % (mapped_bgp_rib_peer)
        else:
            data['error'] = 'There is no bgp rib mapping for that peer: %s' % (peer)
    else:
        data['error'] = 'Not a valid IP addres for peer: %s' % (peer)        

    if rest_api:
        return jsonify(data)
    else:
        return json.dumps(data)


def flattern(A):
    rt = []
    for i in A:
        if isinstance(i,list): rt.extend(flattern(i))
        else: rt.append(i)
    return rt

def analyze_path(**kwargs):
    global logger
    global ribs
    global pnhs

    source_router=kwargs['source_router']
    source_router=source_router.strip()
    ipv4_dst_addr=kwargs['ipv4_dst_addr']
    ipv4_dst_addr=ipv4_dst_addr.strip()
    intermediate_router=kwargs['intermediate_router']
    intermediate_router=intermediate_router.strip()
    weight = kwargs['weight']
    recursion_depth=kwargs['recursion_depth']
    logger.info('Analyzing path from router %s to destination address %s and weight %s - iteration (%s)', intermediate_router,ipv4_dst_addr,weight,recursion_depth)

    try:
        mapped_bgp_rib_peer = bgp_rib_mapping[intermediate_router]
    except Exception, e:
        logger.error('There is not mapping bgp rib for peer: %s', intermediate_router)
        result = {}
        result['endpoint'] = intermediate_router
        result['weight'] = weight
        result['status'] = 'There is not mapping bgp rib for this peer'
        return result

    my_pnhs = ribs[mapped_bgp_rib_peer][ipv4_dst_addr]
    weight_per_pnh = weight / len(my_pnhs)
    logger.debug('Calculating weight %s / len(my_pnhs) %s  =   weight_per_pnh %s', weight,len(my_pnhs),weight_per_pnh)
    
    for dummy, my_pnh in my_pnhs.items():
        if recursion_depth > recursion_depth_max:
            # Recursion depth is too high, we should STOP and notify, about a possible loop or a very long path
            raise ValueError('Max recursion depth reached, warning possible network loop at %s' % intermediate_router)
        elif my_pnh == intermediate_router:
            # Final destination reached (pnh is the intermediate_router, that router is announcing that prefix)
            result = {}
            result['endpoint'] = intermediate_router
            result['weight'] = weight_per_pnh
            result['status'] = 'recursion_ended'
            return [ result ]     
        else:
            #if intermediate_router == source_router:  # first hop analysis
            nhs = pnhs[intermediate_router][my_pnh]
            weight_per_nh = weight_per_pnh / len(nhs)
            logger.debug('Calculating weight_per_pnh %s / len(nhs) %s  =   weight_per_nh %s', weight_per_pnh,len(nhs),weight_per_nh)

            recursion_depth = recursion_depth + 1
            my_result = []
            for nh in nhs:
                endpoint = nh['endpoint']
                weight_per_nh_tmp = weight_per_nh  
                result_tmp = analyze_path(source_router=source_router,ipv4_dst_addr=ipv4_dst_addr,intermediate_router=endpoint,weight=weight_per_nh_tmp,recursion_depth=recursion_depth)
                my_result.append(result_tmp)

            result = flattern(my_result)
            return result
 
@app.route('/network-rib/api/v1.0/analyze_path/<peer_id>/<prefix>',methods=['GET'])
def analyze_path_tmp(peer_id,prefix,rest_api=True):
    global logger
    global ribs
    global pnhs
    initial_weight = 1
    recursion_depth = 1
    source_router = str(peer_id)
    ipv4_dst_addr = str(prefix)
    data = {}

    if valid_ipv4(source_router):
        #data['result'] = 'Its a valid IP addres %s' % (peer)  
        if bgp_rib_mapping.has_key(source_router):
            mapped_bgp_rib_peer = bgp_rib_mapping[source_router]
            if ribs.has_key(mapped_bgp_rib_peer):
                #data['result'] = 'We have a rib for that peer %s' % (peer)
                if valid_ipv4(ipv4_dst_addr):
                    logger.info('Start analyzing path from router %s to destination address %s', source_router,ipv4_dst_addr)
                    try:
                        data['result'] = analyze_path(source_router=source_router,ipv4_dst_addr=ipv4_dst_addr,intermediate_router=source_router,weight=initial_weight,recursion_depth=recursion_depth)
                    except ValueError as err:
                        data['error'] = err.args
                else:
                    data['error'] = 'Not a valid IP addres for peer: %s' % (prefix)
            else:
                data['error'] = 'There is no rib related to bgp mapped peer: %s' % (mapped_bgp_rib_peer)
        else:
            data['error'] = 'There is no bgp rib mapping for that peer: %s' % (peer)   
    else:
        data['error'] = 'Not a valid IP addres for peer: %s' % (peer)  

    if rest_api:
        return jsonify(data)
    else:
        return json.dumps(data)


if __name__ == '__main__':
    update_ribs(rest_api=False)
    update_pnhs(rest_api=False)
    update_bgp_mapping(rest_api=False)
#    a = rib_lookup('192.168.255.3','10.0.0.0',rest_api=False)
#    pprint(a)
#    a = rib_lookup('192.168.255.3','11.0.0.0',rest_api=False)
#    pprint(a)
#    a = rib_lookup('192.168.255.3','20.0.0.0',rest_api=False)
#    pprint(a)
#    a = rib_lookup('192.168.255.3','30.0.0.0',rest_api=False)
#    pprint(a)
#    a=analyze_path_tmp('192.168.255.3','11.0.0.0',rest_api=False)
#    pprint(a)
    app.run(host='0.0.0.0',debug=True)




