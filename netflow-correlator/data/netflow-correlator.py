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

kafka_topic = os.environ['KAFKA_CONSUMER_TOPIC']
kafka_address = socket.gethostbyname(os.environ['KAFKA_ADDR'])
kafka_port = os.environ['KAFKA_PORT']
network_rib_rest_address = socket.gethostbyname(os.environ['NETWORK_RIB_REST_API_ADDR'])
network_rib_rest_port = os.environ['NETWORK_RIB_REST_API_PORT']
network_rib_rest_user = os.environ['NETWORK_RIB_REST_API_USER']
network_rib_rest_password = os.environ['NETWORK_RIB_REST_API_PASSWORD']
network_rib_rest_auth=HTTPBasicAuth(network_rib_rest_user, network_rib_rest_password)
network_rib_rest_api_base_url='http://'+network_rib_rest_address+':'+str(network_rib_rest_port)
statsd_metrics = os.environ['STATSD_METRICS']
statsd_address = os.environ['STATSD_HOST']
statsd_port = os.environ['STATSD_PORT']
path_analysis = os.environ['PATH_ANALYSIS']
#path_analysis = True

statsd_client = statsd.StatsClient(statsd_address, statsd_port)

def check_network_rib_rest_status():
    return True

def netflow_consumer():
    # Consume samples from netflow topic then resolve ip address on related peer rib / peer_hash_id and extract relevant information.
    global peer_hash_ids
    global network_rib_rest_api_base_url
    global network_rib_rest_auth

    consumer = KafkaConsumer(kafka_topic, bootstrap_servers=[ kafka_address+':'+kafka_port ], auto_offset_reset='latest')

    # we should check for check_network_rib_rest_status before continue

    for message in consumer:
        
        json_thing = str(message.value.decode('ascii'))
        netflow_samples = json.loads(json_thing)

        for netflow_sample in netflow_samples:
            #pprint (netflow_sample)
            netflow_host = netflow_sample['peer_ip_src']
            ipv4_dst_addr = netflow_sample['ip_dst']
            netflow_timestamp_received = netflow_sample['stamp_updated']
            packets_sent = netflow_sample['packets']
            bytes_sent = netflow_sample['bytes']
            # fisrt check for theorical matrix
            rib_lookup_url = network_rib_rest_api_base_url+'/network-rib/api/v1.0/rib_lookup/'+netflow_host+'/'+ipv4_dst_addr
            resp = requests.get(rib_lookup_url)
            if resp.status_code != 200:
                # This means something went wrong.
                #raise ApiError('GET /tasks/ {}'.format(resp.status_code))
                statsd_client.incr('netflow.stats,result=resp_api_fail,action=iplookup')
                pass 
            else:            
                rib_lookup_resp = resp.json()
                if not rib_lookup_resp:
                    print 'No response from this request (%s)' % (rib_lookup_url)
                    statsd_client.incr('netflow.stats,result=empty,action=rib_lookup')
                else:
                    try:
                        if rib_lookup_resp.has_key('pnh'):
                            bgp_next_hop = rib_lookup_resp['pnh']
                            statsd_client.incr('netflow.stats,result=succeed,action=iplookup')
                            statsd_client.incr('netflow.theorical_matrix_bytes,src_PE='+netflow_host+',dst_PE='+bgp_next_hop,count=bytes_sent)
                            statsd_client.incr('netflow.theorical_matrix_packets,src_PE='+netflow_host+',dst_PE='+bgp_next_hop,count=packets_sent)   
                            print 'netflow_timestamp_received %s, netflow_host %s, ipv4_dst_addr: %s, bgp_next_hop %s' %  (netflow_timestamp_received,netflow_host,ipv4_dst_addr, bgp_next_hop)
                            if path_analysis:
                                path_analysis_url = network_rib_rest_api_base_url+'/network-rib/api/v1.0/analyze_path/'+netflow_host+'/'+ipv4_dst_addr
                                resp = requests.get(path_analysis_url)
                                #print 'Start path analysis %s' % path_analysis_url
                                if resp.status_code != 200:
                                    print 'No response from this request (%s)' % (path_analysis_url)
                                    statsd_client.incr('netflow.stats,result=empty,action=analyze_path')
                                else:
                                    path_analysis_resp = resp.json()
                                    #print "going into else"
                                    if path_analysis_resp.has_key('error'):
                                        print 'Error message returned:  %s' % (path_analysis_resp['error'])
                                        statsd_client.incr('netflow.stats,result=error,action=analyze_path')
                                    elif path_analysis_resp.has_key('result'):
                                        endpoints = path_analysis_resp['result']
                                        #print "Path analysis result %s" % endpoints
                                        for endpoint in endpoints:
                                            weighted_bytes_sent = packets_sent * endpoint['weight']
                                            weighted_packets_sent = packets_sent * endpoint['weight']
                                            dst_PE = endpoint['endpoint']
                                            print "A fraction of %s from %s to %s is sent via %s" % (weighted_packets_sent, netflow_host, ipv4_dst_addr, dst_PE)
                                            statsd_client.incr('netflow.real_matrix_bytes,src_PE='+netflow_host+',dst_PE='+dst_PE,count=weighted_bytes_sent)   
                                            statsd_client.incr('netflow.real_matrix_packets,src_PE='+netflow_host+',dst_PE='+dst_PE,count=weighted_packets_sent)   

                        else:
                            print "No routes found for route %s in router %s" % (ipv4_dst_addr,netflow_host,)
                            statsd_client.incr('netflow.stats,result=no-route,action=iplookup')                            
                    except Exception, e:
                        print 'This exception arise %s' % (str(e))
                        statsd_client.incr('netflow.stats,result=exception,action=iplookup')
                        print 'netflow_timestamp_received %s, netflow_host %s, ipv4_dst_addr: %s' %  (netflow_timestamp_received,netflow_host, ipv4_dst_addr)
                        pprint(get_peer_lookup_resp)
                        exit(0) #

# Wait until network-rib-api is available
while not check_network_rib_rest_status():
    print "network rib service not available yet, sleeping..."
    time.sleep(5)
netflow_consumer()

