#!/usr/bin/python
import os
import socket
import json
from pprint import pprint
from kafka import KafkaConsumer
from kafka import KafkaProducer
from kafka.errors import KafkaError
import threading
import pytricia
import time
import requests
from requests.auth import HTTPBasicAuth
import statsd
import logging
import logging.handlers

lock = threading.Lock() 
peer_hash_ids = {}

kafka_topic = os.environ['KAFKA_CONSUMER_TOPIC']
kafka_address = socket.gethostbyname(os.environ['KAFKA_ADDR'])
kafka_port = os.environ['KAFKA_PORT']

openbmp_rest_address = socket.gethostbyname(os.environ['OPENBMP_REST_ADDR'])
openbmp_rest_port = os.environ['OPENBMP_REST_PORT']
openbmp_rest_user = os.environ['OPENBMP_REST_USER']
openbmp_rest_password = os.environ['OPENBMP_REST_PASSWORD']
openbmp_rest_auth=HTTPBasicAuth(openbmp_rest_user, openbmp_rest_password)
openbmp_rest_api_base_url='http://'+openbmp_rest_address+':'+openbmp_rest_port

#nexthop_resolver_address = os.environ['NEXTHOP_RESOLVER_ADDR']
#nexthop_resolver_port = os.environ['NEXTHOP_RESOLVER_PORT']
#nexthop_resolver_rest_api_base_url='http://'+nexthop_resolver_address+':'+nexthop_resolver_port

statsd_metrics = os.environ['STATSD_METRICS']
statsd_address = os.environ['STATSD_HOST']
statsd_port = os.environ['STATSD_PORT']

recursion_depth_max = 15

#kafka_topic = 'netflow'
#kafka_address = 'kafka'
#kafka_port = '9092'
#openbmp_rest_address = 'mysql'
#openbmp_rest_port = '8001'
#openbmp_rest_user = "openbmp"
#openbmp_rest_password = "CiscoRA"
#openbmp_rest_auth=HTTPBasicAuth(openbmp_rest_user, openbmp_rest_password)
#rest_api_base_url='http://'+openbmp_rest_address+':'+openbmp_rest_port
#statsd_address = '172.30.121.19'
#statsd_port = 8125
##statsd_username = "juniper"
##statsd_password = "juniper"
statsd_client = statsd.StatsClient(statsd_address, statsd_port)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_peer_hash_ids():
    # Refresh peer_hash_ids dictionary each X seconds
    global peer_hash_ids
    global rest_api_base_url
    global openbmp_rest_auth

    get_peer_url = openbmp_rest_api_base_url+'/db_rest/v1/peer'
    #http://172.30.121.19:8001/db_rest/v1/peer

    resp = requests.get(get_peer_url, auth=openbmp_rest_auth)
    if resp.status_code != 200:
        logger.error('We got wrong status code (%s) from this rest api request (%s)', resp.status_code,get_peer_lookup_url)
        statsd_client.incr('netflow.stats,result=empty,action=rest_api_error')
    else:
        get_peer_resp = resp.json()
        if get_peer_resp['v_peers']['size'] == 0:
            logger.error('No bgp peers found')
        else:
            with lock:
                peer_hash_ids.clear() 
                for peer in get_peer_resp['v_peers']['data']:
                    try:
                        if peer['isUp'] == 1:
                            peer_ip = peer['PeerIP']
                            peer_hash_id = peer['peer_hash_id']
                            peer_hash_ids[peer_ip]=peer_hash_id
                    except e:
                        pass
                    # Need to arise an exception about something is wrong with json content
            logger.info('Found %s bgp peers', len(peer_hash_id))

    # Send a small report to syslog/notification  about how many peers or even a pprint peer_hash_ids

def netflow_consumer():
    # Consume samples from netflow topic then resolve ip address on related peer rib / peer_hash_id and extract relevant information.
    global peer_hash_ids
    global rest_api_base_url
    global openbmp_rest_auth
    global logger
    
    consumer = KafkaConsumer(kafka_topic, bootstrap_servers=[ kafka_address+':'+kafka_port ], auto_offset_reset='latest')
    #    We need to test connectivity with bmp_DB, it does not make sense start reading kafka until we have a proper access to bgp information
    for message in consumer:

        json_thing = str(message.value.decode('ascii'))
        netflow_samples = json.loads(json_thing)
        statsd_client.incr('netflow.stats,result=succeed,action=iplookup')

        for netflow_sample in netflow_samples:
            netflow_host = netflow_sample['peer_ip_src']
            ipv4_dst_addr = netflow_sample['ip_dst']
            bytes_sent = netflow_sample['bytes']
            packets_sent = netflow_sample['packets']
            netflow_timestamp_received = netflow_sample['stamp_inserted']
            logger.info('Analyzing path for source_router=%s,ipv4_dst_addr=%s,intermediate_router=%s,bytes_sent=%s, packets_sent=%s',netflow_host,ipv4_dst_addr,netflow_host,bytes_sent,packets_sent)
            analyze_path(source_router=netflow_host,ipv4_dst_addr=ipv4_dst_addr,intermediate_router=netflow_host,bytes_sent=bytes_sent, packets_sent=packets_sent, recursion_depth=0)

def bgp_ipv4_lookup (**kwargs):

    global logger
    router=kwargs['router']
    ipv4_addr=kwargs['ipv4_addr']
    bgp_routes = []

    if peer_hash_ids.has_key(router):
        peer_hash_id = peer_hash_ids[router]
        
        get_peer_lookup_url = openbmp_rest_api_base_url+'/db_rest/v1/rib/peer/'+peer_hash_id+'/lookup/'+ipv4_addr
        #http://172.30.121.19:8001/db_rest/v1/rib/peer/4d2a478db51525ee9ffcef8483a1e0fd/lookup/20.0.12.81
        logger.info('Performing rest api request: %s', get_peer_lookup_url)
        resp = requests.get(get_peer_lookup_url, auth=openbmp_rest_auth)
        
        if resp.status_code != 200:
            logger.error('We got wrong status code (%s) from this rest api request (%s)', resp.status_code,get_peer_lookup_url)
            statsd_client.incr('netflow.stats,result=empty,action=rest_api_error')
        else:            
            get_peer_lookup_resp = resp.json()
            if not get_peer_lookup_resp:
                logger.warn('No bgp route received from %s, matches with %s', router,ipv4_addr)
                statsd_client.incr('netflow.stats,result=empty,action=iplookup')
            else:
                try:
                    if get_peer_lookup_resp['v_routes']['size'] == 0:
                        logger.warn('No routes found for %s in %s rib', router,ipv4_dst_addr)
                        statsd_client.incr('netflow.stats,result=no-route,action=iplookup')
                    else:
                        for bgp_route in get_peer_lookup_resp['v_routes']['data']:
                            if bgp_route['isWithdrawn'] == 'false':
                                bgp_route_tmp = {}
                                bgp_route_tmp['NH'] = bgp_route['NH']
                                bgp_route_tmp['AS_Path'] = bgp_route['AS_Path']
                                bgp_route_tmp['PeerAddress'] = bgp_route['PeerAddress']
                                bgp_route_tmp['Prefix'] = bgp_route['Prefix']
                                bgp_route_tmp['PrefixLen'] = bgp_route['PrefixLen']
                                
                                statsd_client.incr('netflow.stats,result=succeed,action=iplookup')
                                bgp_routes.append(bgp_route_tmp)
                                logger.info('BGP route found (%s) on router %s  with nexthop %s', ipv4_addr,router,bgp_route_tmp['NH'])
                            else:
                                statsd_client.incr('netflow.stats,result=withdrawn,action=iplookup')
                                logger.warn('The bgp route that matches %s from bgp peer %s is not valid, was withdrawn', ipv4_addr,router)
                                statsd_client.incr('netflow.stats,result=withdrawn,action=iplookup')
                except Exception, e:
                    logger.error('This exception arise : %s', e)
                    statsd_client.incr('netflow.stats,result=exception,action=iplookup')
                    pass
                    
    else:
        logger.error('No bgp peer session found from this host %s', router)
        statsd_client.incr('netflow.stats,result=no-bgp-session,action=iplookup')
    logger.info('Returning this list of nexthosts %s', bgp_routes)
    return bgp_routes

def resolve_bgp_nexthop (**kwargs):
    global logger
    router=kwargs['router']
    ipv4_addr=kwargs['ipv4_addr']
    nexthops = []
    rib={}
    rib['192.168.255.1']={
        '192.168.255.1':[ { 'link_name':'igp', 'endpoint':'192.168.255.1'} ], 
        '192.168.255.2':[ { 'link_name':'igp', 'endpoint':'192.168.255.2'} ], 
        '192.168.255.3':[ { 'link_name':'igp', 'endpoint':'192.168.255.3'} ]
    }
    rib['192.168.255.2']={
        '192.168.255.1':[ { 'link_name':'igp', 'endpoint':'192.168.255.1'} ], 
        '192.168.255.2':[ { 'link_name':'igp', 'endpoint':'192.168.255.2'} ], 
        '192.168.255.3':[ { 'link_name':'igp', 'endpoint':'192.168.255.3'} ]
    }
    rib['192.168.255.3']={
        '192.168.255.1':[ { 'link_name':'igp', 'endpoint':'192.168.255.1'} ], 
        '192.168.255.2':[ { 'link_name':'igp', 'endpoint':'192.168.255.2'} ], 
        '192.168.255.3':[ { 'link_name':'igp', 'endpoint':'192.168.255.3'} ]
    }

    return rib[router][ipv4_addr]



    #get_nexthop_url = nexthop_resolver_rest_api_base_url+'/db_rest/v1/peer'
    ##http://172.30.121.19:8001/db_rest/v1/peer
#
    #resp = requests.get(get_peer_url, auth=openbmp_rest_auth)
    #if resp.status_code != 200:
    #    logger.error('We got wrong status code (%s) from this rest api request (%s)', resp.status_code,get_peer_lookup_url)
    #    statsd_client.incr('netflow.stats,result=empty,action=rest_api_error')
    #else:
    #    get_peer_resp = resp.json()
    #    if get_peer_resp['v_peers']['size'] == 0:
    #        logger.error('No bgp peers found')
    #    else:
    #        with lock:
    #            peer_hash_ids.clear() 
    #            for peer in get_peer_resp['v_peers']['data']:
    #                try:
    #                    if peer['isUp'] == 1:
    #                        peer_ip = peer['PeerIP']
    #                        peer_hash_id = peer['peer_hash_id']
    #                        peer_hash_ids[peer_ip]=peer_hash_id
    #                except e:
    #                    pass
    #                # Need to arise an exception about something is wrong with json content
    #        logger.info('Found %s bgp peers', len(peer_hash_id))
#
def analyze_path(**kwargs):
    global logger
    source_router=kwargs['source_router']
    ipv4_dst_addr=kwargs['ipv4_dst_addr']
    intermediate_router=kwargs['intermediate_router']
    bytes_sent=kwargs['bytes_sent']
    packets_sent=kwargs['packets_sent']
    recursion_depth=kwargs['recursion_depth']

    bgp_routes = []
    bgp_routes = bgp_ipv4_lookup(router=intermediate_router, ipv4_addr=ipv4_dst_addr)
   
    ############
    #NOTE:  bgp_routes is a list of bgp_route with the following content    
    #bgp_route['NH'] 
    #bgp_route['AS_Path']
    #bgp_route['PeerAddress'] 
    #bgp_route['Prefix'] 
    #bgp_route['PrefixLen']   
    ############
    if bgp_routes:   # Need to confirm if this really match a non-empty dict
        for bgp_route in bgp_routes:
            bytes_sent_per_route = bytes_sent / len(bgp_routes)
            packets_sent_per_route = packets_sent / len(bgp_routes)

            if recursion_depth > recursion_depth_max:
                # Recursion depth is too high, we should STOP and notify, about a possible loop or a very long path
                tags='src_PE='+str(source_router)+', dst_PE='+str(intermediate_router)+',recursion='+str(recursion_depth)
                statsd_client.incr('netflow.real.bytes,'+tags,count=bytes_sent_per_route)
                statsd_client.incr('netflow.real.packets,'+tags,count=packets_sent_per_route)
            elif bgp_route['NH'] == intermediate_router:
                # update the practical matrix with source_router|intermediate_router|bytes_per_bgp_nh|packets_per_bgp_nh               
                tags='src_PE='+str(source_router)+', dst_PE='+str(intermediate_router)+',recursion='+str(recursion_depth)
                statsd_client.incr('netflow.real.bytes,'+tags,count=bytes_sent_per_route)
                statsd_client.incr('netflow.real.packets,'+tags,count=packets_sent_per_route)

                # there is a special case if the fist-hop is the final-host
                if intermediate_router == source_router:   # first hop analysis
                    # update the theorical matrix with source_router|bgp_nh|bytes_per_bgp_nh|packets_per_bgp_nh
                    tags='src_PE='+str(source_router)+', dst_PE='+str(intermediate_router)+',recursion='+str(recursion_depth)
                    statsd_client.incr('netflow.theorical.bytes,'+tags,count=bytes_sent_per_route)
                    statsd_client.incr('netflow.theorical.packets,'+tags,count=packets_sent_per_route)
            else:
                if intermediate_router == source_router:  # first hop analysis
                    # update the theorical matrix with source_router|bgp_nh|bytes_per_bgp_nh|packets_per_bgp_nh
                    tags='src_PE='+str(source_router)+', dst_PE='+str(bgp_route['NH'])+',recursion='+str(recursion_depth)
                    statsd_client.incr('netflow.theorical.bytes,'+tags,count=bytes_sent_per_route)
                    statsd_client.incr('netflow.theorical.packets,'+tags,count=packets_sent_per_route)
                
                next_hops = resolve_bgp_nexthop(router=intermediate_router,ipv4_addr=bgp_route['NH'])
                # Look for possible install routes to lsp
                
                bytes_sent_per_next_hop = bytes_sent_per_route / len(next_hops)
                packets_sent_per_next_hop = packets_sent_per_route / len(next_hops)

                for next_hop in next_hops:
                    logger.info('my nexthop to recurse %s', next_hop)
                    link_name = next_hop['link_name']  # this is the link or neighbor
                    endpoint = next_hop['endpoint']
                    # update per-LSP matrix with lsp_name
                    tags='src_PE=' + str(source_router) + ', ' \
                         'dst_PE=' + str(bgp_route['NH']) + ', ' \
                         'recursion=' + str(recursion_depth) + ', ' \
                         'link_name=' + str(link_name) + ', ' \
                         'endpoint_A=' + str(intermediate_router) + ', ' \
                         'endpoint_B=' + str(endpoint) + ', ' \
                         'recursion=' + str(recursion_depth)
                    statsd_client.incr('netflow.link_stats.bytes,'+tags,count=bytes_sent_per_route)
                    statsd_client.incr('netflow.link_stats.packets,'+tags,count=packets_sent_per_route)
                    recursion_depth = recursion_depth + 1
                    analyze_path(source_router=source_router,ipv4_dst_addr=ipv4_dst_addr,intermediate_router=endpoint,bytes_sent=bytes_sent_per_next_hop,packets_sent=packets_sent_per_next_hop,recursion_depth=recursion_depth)

    else:
        logger.error('No bgp route found from %s, to %s', source_router,ipv4_dst_addr)

#threads = [threading.Thread(target=netflow_consumer), threading.Thread(target=get_peer_hash_ids)]

#for t in threads:
#    t.daemon = True    
#    t.start()
#for t in threads:
#    t.join()
get_peer_hash_ids()
netflow_consumer()