#!usr/bin/python
from flask import Flask, jsonify
import pytricia
from netaddr import valid_ipv4
from priodict import priorityDictionary
import os
import threading
import socket
import time
import requests
from requests.auth import HTTPBasicAuth

import logging
import logging.handlers

app = Flask(__name__)

class AutoVivification(dict):
    """Implementation of perl's autovivification feature."""
    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            value = self[item] = type(self)()
            return value

lock = threading.Lock()
ribs = {}
pnhs = {}
status = {}

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


recursion_depth_max = 15

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
def get_link_state_graph():
    
    # Refresh peer_hash_ids dictionary each X seconds
    link_state_graph = AutoVivification()
    global openbmp_rest_api_base_url
    global openbmp_rest_auth
    get_peer_url = openbmp_rest_api_base_url+'/db_rest/v1/linkstate/links'
    #http://172.30.121.19:8001/db_rest/v1/peer
    lista = []
    resp = requests.get(get_peer_url, auth=openbmp_rest_auth)
    if resp.status_code != 200:
        # This means something went wrong.
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))
    else:
        get_linkstate_resp = resp.json()
        with lock:
            link_state_graph.clear() 
            for peer in get_linkstate_resp['v_ls_links']['data']:
                try:
                    # In case of parallel links with diferent metrics
                    if link_state_graph[peer['Local_RouterId']].has_key(peer['Remote_RouterId']):
                        if link_state_graph[peer['Local_RouterId']][peer['Remote_RouterId']] > peer['igp_metric']:
                            link_state_graph[peer['Local_RouterId']][peer['Remote_RouterId']] = peer['igp_metric']                            
                    else:
                        link_state_graph[peer['Local_RouterId']][peer['Remote_RouterId']] = peer['igp_metric']
                except Exception as e:
                    pass               
    return link_state_graph

def _dijkstra(g,start,end=None):
 
    d = {}  # dictionary of final distances
    p = {}  # dictionary of predecessors
    q = priorityDictionary()   # est.dist. of non-final vert.
    q[start] = 0
    for v in q:
        d[v] = q[v]
        if v == end: break      
        for w in g[v]:
            vwLength = d[v] + g[v][w]
            if w in d:
                if vwLength < d[w]:
                    raise ValueError, \
  "Dijkstra: found better path to already-final vertex"
            elif w not in q or vwLength < q[w]:
                q[w] = vwLength
                p[w] = v
            #elif  w not in q or vwLength == q[w]:
            #    q[w] = vwLength
            #    p[w] += [v] 
    return (d,p)


def _shortestPath(G,start,end):
    d,p = _dijkstra(G,start,end)
    path = []
    while 1:
        path.append(end)
        print end
        if end == start: break
        end = p[end]
    path.reverse()
    return path
 

def get_peer_hash_ids():
    # Refresh peer_hash_ids dictionary for latter usage 
    global rest_api_base_url
    global openbmp_rest_auth
    global logger
    global openbmp_rest_auth
    global openbmp_rest_api_base_url
    peer_hash_ids = {}


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
    return peer_hash_ids
    # Send a small report to syslog/notification  about how many peers or even a pprint peer_hash_ids


@app.route('/network-rib/api/v1.0/status')
def status():
#   It would be nice to ask the rest api about what is he doing, however if we
# are single thread/single core, I thing it would be as useful as I would like to be
    global status
    peer_hash_ids = get_peer_hash_ids()
    data['result'] = peer_hash_ids
    return jsonify(data)

@app.route('/network-rib/api/v1.0/next_hop_resolve')
def next_hop_resolve():
    global next_hop_resolve
    result = AutoVivification()
    graph = get_link_state_graph()
    nodes = graph.keys()
    for nodeA in nodes:
        for nodeB in nodes:
            if nodeB != nodeA:
                result[nodeA][nodeB] = _shortestPath(graph,nodeA,nodeB)[1]
    return jsonify(result)            

#@app.route('/network-rib/api/v1.0/update-rib',methods=['GET'])
#def update_rib():
##  This api call, will update a temporary data structure and in the end it will
##  replace the real data structure for ribs and pnhs
#
#    global ribs
#    global pnhs
#    global status
#    peer_hash_ids = {}
#    ribs_tmp = {}
#    phnh_tmp = {}
#
#
## For each bgp_peer
#   # gel All rib, 
#        # populate ribs with prefix + pnh
#        # populate pnhs with just pnhs
#        # use the maping file to copy/clone clients with related RR
## For each bgp peer on ribs
#    # for each pnh on pnhs['bgp-peer'
#        # resolve pnh on install
#        # if not
#        # resolve pnh on igp
#        # populate ALL nh on ribs and pnh tables (calculate weitgs or %)
#
#
#    if ribs empty
#        status['api_ready'] = False
#    else:
#        status['api_ready'] = True
#    status['updating_rib'] = True
#
#    peer_hash_ids = get_peer_hash_ids()
#
#    for peer_ip in peer_hash_ids.keys():
#        ribs_tmp[peer_ip], pnhs_tmp[peer_ip] = get_rib_from_peer(peer=peer_ip)
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


if __name__ == '__main__':
    app.run(debug=True,port=4000)

