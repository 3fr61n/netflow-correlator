import json
import requests
from requests.auth import HTTPBasicAuth
from priodict import priorityDictionary
import socket
import threading
import pprint 
from collections import defaultdict
import pytricia
import sys
import os


openbmp_rest_address = '172.30.121.19'
openbmp_rest_port = '8001'
openbmp_rest_user = 'openbmp'
openbmp_rest_password = 'CiscoRA'
openbmp_rest_auth=HTTPBasicAuth(openbmp_rest_user, openbmp_rest_password)
openbmp_rest_api_base_url='http://'+openbmp_rest_address+':'+openbmp_rest_port

lock = threading.Lock()
link_state_graph = {}


class AutoVivification(dict):
	"""Implementation of perl's autovivification feature."""
	def __getitem__(self, item):
		try:
			return dict.__getitem__(self, item)
		except KeyError:
			value = self[item] = type(self)()
			return value

def get_link_state_graph():
	
	# Refresh peer_hash_ids dictionary each X seconds
	link_state_graph = AutoVivification()
	global openbmp_rest_api_base_url
	global openbmp_rest_auth
	get_peer_url = openbmp_rest_api_base_url+'/db_rest/v1/linkstate/links'
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

def Dijkstra(g,start,end=None):
 
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
					raise ValueError
			elif w not in q or vwLength < q[w]:
				q[w] = vwLength
				p[w] = [v]
			elif  w not in q or vwLength == q[w]:
				q[w] = vwLength
				p[w] += [v] 
	return (d,p)

def _shortestPath(g,start,end):
	
	d,p = Dijkstra(g,start,end)
	print p
	path = [[end]]
	while True:
		if len(p[end]) > 1:
			path.append(p[end])
			for node in p[end]:
				if node != start:
					if ''.join(p[end]) == start: break
					end = node
		path.append(p[end])
		if ''.join(p[end]) == start: break
		end = ''.join(p[end])   
	return path[::-1]


def main():

	if getattr(sys, 'frozen', False):
		# frozen
		BASE_DIR = os.path.dirname(sys.executable)
	else:
		# unfrozen
		BASE_DIR = os.path.dirname(os.path.realpath(__file__))

	dirpath = BASE_DIR + '/igp-resolve/'
	filename = 'igp_resolve.json'
	path = os.path.join (dirpath,filename)			
	# Create directory if does not exist
	if not os.path.exists (dirpath):
		os.makedirs (dirpath,mode=0777)

	result = AutoVivification()
	graph = get_link_state_graph()
	nodes = graph.keys()
	for nodeA in nodes:
		for nodeB in nodes:
			if nodeB != nodeA:
				result[nodeA][nodeB] = {nodeA:{'endpoint':_shortestPath(graph,nodeA,nodeB)[1],'install':'','lsp_name':''}}
	#return result
	with open (path,'w') as outfile:		
		json.dump(result,outfile)

if __name__ == '__main__':

	main()


