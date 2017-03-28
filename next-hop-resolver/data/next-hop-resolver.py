#!/usr/bin/env python
import json
import requests
from requests.auth import HTTPBasicAuth
from priodict import priorityDictionary
import socket
import threading
import pprint 

graph = {
'N1': {'N2': 1},
'N12':{'N13':1},
'N2': {'N4': 1, 'N13':1},
'N4': {'N5': 1, 'N12': 1},
'N5': {'N6': 1},
'N6': {'N7': 1},
'N7': {'N8': 1},
'N8': {'N9':1},
'N9': {'N10': 1, 'N11': 1, 'N12':1},
'N10': {'N11':1},
'N11': {'N12':1},
'N13':{'N12':1}
}

# 'R1': {'R2':1}
# 'Local_Router_Name' : {'Remote_Router_Name':igp_metric}

#      - "KAFKA_ADDR=kafka"
#      - "KAFKA_PORT=9092"
#      - "KAFKA_CONSUMER_TOPIC=netflow_1"
#      - "OPENBMP_REST_ADDR=bmp_db_1"
#      - "OPENBMP_REST_PORT=8001"
#      - "OPENBMP_REST_USER=openbmp"
#      - "OPENBMP_REST_PASSWORD=CiscoRA"
#      - "STATSD_METRICS=true"
#      - "STATSD_HOST=172.30.121.19"
#      - "STATSD_PORT=8125"

# Dijkstra's algorithm for shortest paths
# David Eppstein, UC Irvine, 4 April 2002

openbmp_rest_address = '172.30.121.19'
openbmp_rest_port = '8001'
openbmp_rest_user = 'openbmp'
openbmp_rest_password = 'CiscoRA'
openbmp_rest_auth=HTTPBasicAuth(openbmp_rest_user, openbmp_rest_password)
rest_api_base_url='http://'+openbmp_rest_address+':'+openbmp_rest_port

lock = threading.Lock()
link_state_graph = {}

def get_link_state_graph():
    
    # Refresh peer_hash_ids dictionary each X seconds
    global link_state_graph
    global rest_api_base_url
    global openbmp_rest_auth

    get_peer_url = rest_api_base_url+'/db_rest/v1/linkstate/links'
    #http://172.30.121.19:8001/db_rest/v1/peer

    resp = requests.get(get_peer_url, auth=openbmp_rest_auth)
    if resp.status_code != 200:
        # This means something went wrong.
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))
    else:
        get_linkstate_resp = resp.json()
        #pprint.pprint (get_linkstate_resp)
        
        #if get_linkstate_resp['data']['Remote_RouterId'] == 0:
        #    print("No bgp peers found")
        #else:
        with lock:
            link_state_graph.clear() 
            for peer in get_linkstate_resp['v_ls_links']['data']:
                try:
                    #'Local_Router_Name' : {'Remote_Router_Name':igp_metric}
                    local =  peer['Local_RouterId']
                    remote = peer ['Remote_RouterId']
                    link_state_graph[local] = {remote:peer ['igp_metric']} 
                    #if peer['isUp'] == 1:
                    #    peer_ip = peer['PeerIP']
                    #    peer_hash_id = peer ['peer_hash_id']
                    #    peer_hash_ids[peer_ip]=peer_hash_id
                except Exception as e:
                    pass
    return link_state_graph

def Dijkstra(G,start,end=None):
    """
    Find shortest paths from the start vertex to all
    vertices nearer than or equal to the end.

    The input graph G is assumed to have the following
    representation: A vertex can be any object that can
    be used as an index into a dictionary.  G is a
    dictionary, indexed by vertices.  For any vertex v,
    G[v] is itself a dictionary, indexed by the neighbors
    of v.  For any edge v->w, G[v][w] is the length of
    the edge.  This is related to the representation in
    <http://www.python.org/doc/essays/graphs.html>
    where Guido van Rossum suggests representing graphs
    as dictionaries mapping vertices to lists of neighbors,
    however dictionaries of edges have many advantages
    over lists: they can store extra information (here,
    the lengths), they support fast existence tests,
    and they allow easy modification of the graph by edge
    insertion and removal.  Such modifications are not
    needed here but are important in other graph algorithms.
    Since dictionaries obey iterator protocol, a graph
    represented as described here could be handed without
    modification to an algorithm using Guido's representation.

    Of course, G and G[v] need not be Python dict objects;
    they can be any other object that obeys dict protocol,
    for instance a wrapper in which vertices are URLs
    and a call to G[v] loads the web page and finds its links.
    
    The output is a pair (D,P) where D[v] is the distance
    from start to v and P[v] is the predecessor of v along
    the shortest path from s to v.
    
    Dijkstra's algorithm is only guaranteed to work correctly
    when all edge lengths are positive. This code does not
    verify this property for all edges (only the edges seen
    before the end vertex is reached), but will correctly
    compute shortest paths even for some graphs with negative
    edges, and will raise an exception if it discovers that
    a negative edge has caused it to make a mistake.
    """

    D = {}  # dictionary of final distances
    P = {}  # dictionary of predecessors
    Q = priorityDictionary()   # est.dist. of non-final vert.
    Q[start] = 0
    
    for v in Q:
        D[v] = Q[v]
        if v == end: break
        
        for w in G[v]:
            vwLength = D[v] + G[v][w]
            if w in D:
                if vwLength < D[w]:
                    raise ValueError, \
  "Dijkstra: found better path to already-final vertex"
            elif w not in Q or vwLength < Q[w]:
                Q[w] = vwLength
                P[w] = v
    
    return (D,P)
            
def shortestPath(G,start,end):
    """
    Find a single shortest path from the given start vertex
    to the given end vertex.
    The input has the same conventions as Dijkstra().
    The output is a list of the vertices in order along
    the shortest path.
    """

    D,P = Dijkstra(G,start,end)
    Path = []
    while 1:
        Path.append(end)
        if end == start: break
        end = P[end]
    Path.reverse()
    return Path



print type(graph)
print get_link_state_graph()
kk = get_link_state_graph()
nodes =  kk.keys()

for nodeA in nodes:
    for nodeB in nodes:
        print nodeA,nodeB
        #shortestPath(kk,nodeA,nodeB)
#print shortestPath(kk,nodeA,nodeB)
#print result

print shortestPath(kk, '192.168.255.1','192.168.255.3')
#print shortestPath(graph, 'N1','N12')
