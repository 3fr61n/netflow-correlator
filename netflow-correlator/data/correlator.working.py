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
rest_api_base_url='http://'+openbmp_rest_address+':'+openbmp_rest_port
statsd_metrics = os.environ['STATSD_METRICS']
statsd_address = os.environ['STATSD_HOST']
statsd_port = os.environ['STATSD_PORT']


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



def get_peer_hash_ids():
    # Refresh peer_hash_ids dictionary each X seconds
    global peer_hash_ids
    global rest_api_base_url
    global openbmp_rest_auth

    get_peer_url = rest_api_base_url+'/db_rest/v1/peer'
    #http://172.30.121.19:8001/db_rest/v1/peer

    resp = requests.get(get_peer_url, auth=openbmp_rest_auth)
    if resp.status_code != 200:
        # This means something went wrong.
        raise ApiError('GET /tasks/ {}'.format(resp.status_code))
    else:
        get_peer_resp = resp.json()
        #pprint (get_peer_resp)
        if get_peer_resp['v_peers']['size'] == 0:
            print("No bgp peers found")
        else:
            with lock:
                peer_hash_ids.clear() 
                for peer in get_peer_resp['v_peers']['data']:
                    try:
                        if peer['isUp'] == 1:
                            peer_ip = peer['PeerIP']
                            peer_hash_id = peer ['peer_hash_id']
                            peer_hash_ids[peer_ip]=peer_hash_id
                    except e:
                        pass
                    # Need to arise an exception about something is wrong with json content

    # Send a small report to syslog/notification  about how many peers or even a pprint peer_hash_ids
    #pprint(peer_hash_ids)

def netflow_consumer():
    # Consume samples from netflow topic then resolve ip address on related peer rib / peer_hash_id and extract relevant information.
    global peer_hash_ids
    global rest_api_base_url
    global openbmp_rest_auth

    consumer = KafkaConsumer(kafka_topic, bootstrap_servers=[ kafka_address+':'+kafka_port ], auto_offset_reset='latest')

#    We need to test connectivity with bmp_DB, it does not make sense start reading kafka until we have a proper access to bgp information

    for message in consumer:

        json_thing = str(message.value.decode('ascii'))
        netflow_samples = json.loads(json_thing)
        statsd_client.incr('netflow.stats,result=succeed,action=iplookup')
#        pprint(netflow_sample)
# for netflow input
#        netflow_host = netflow_sample['host']
#        ipv4_dst_addr = netflow_sample['ipv4_dst_addr']
#        netflow_timestamp_received = netflow_sample['timestamp']
# for pmacctt input

        for netflow_sample in netflow_samples:
            #pprint (netflow_sample)
            netflow_host = netflow_sample['peer_ip_src']
            ipv4_dst_addr = netflow_sample['ip_dst']
            netflow_timestamp_received = netflow_sample['stamp_inserted']

            if peer_hash_ids.has_key(netflow_host):
                peer_hash_id = peer_hash_ids[netflow_host]
#                print 'netflow_timestamp_received %s, netflow_host %s, ipv4_dst_addr: %s, peer_hash_id: %s' %  (netflow_timestamp_received,netflow_host, ipv4_dst_addr, peer_hash_id)
                get_peer_lookup_url = rest_api_base_url+'/db_rest/v1/rib/peer/'+peer_hash_id+'/lookup/'+ipv4_dst_addr
                #http://172.30.121.19:8001/db_rest/v1/rib/peer/4d2a478db51525ee9ffcef8483a1e0fd/lookup/20.0.12.81
                resp = requests.get(get_peer_lookup_url, auth=openbmp_rest_auth)
                if resp.status_code != 200:
                    # This means something went wrong.
                    raise ApiError('GET /tasks/ {}'.format(resp.status_code))
                else:            
                    get_peer_lookup_resp = resp.json()
                    if not get_peer_lookup_resp:
                        print 'No bgp route received from %s, matches with %s' % (netflow_host,ipv4_dst_addr)
                        statsd_client.incr('netflow.stats,result=empty,action=iplookup')
                    else:
                        try:
                            #pprint(get_peer_lookup_resp['v_routes']['size'])
                            if get_peer_lookup_resp['v_routes']['size'] == 0:
                                print("No routes found")
                                statsd_client.incr('netflow.stats,result=no-route,action=iplookup')
                            else:
                                for route in get_peer_lookup_resp['v_routes']['data']:
                                    if route['isWithdrawn'] == 'false':
                                        bgp_next_hop = route['NH']
                                        statsd_client.incr('netflow.stats,result=succeed,action=iplookup')
                                        print 'netflow_timestamp_received %s, netflow_host %s, ipv4_dst_addr: %s, bgp_next_hop %s, peer_hash_id: %s' %  (netflow_timestamp_received,netflow_host,ipv4_dst_addr, bgp_next_hop, peer_hash_id)
                                    else:
                                        statsd_client.incr('netflow.stats,result=withdrawn,action=iplookup')
                                        print "The bgp route that matches %s from bgp peer %s is not valid, was withdrawn"  %  (ipv4_dst_addr,netflow_host)
                                        pprint(get_peer_lookup_resp)
                        except Exception, e:
                            print 'This exception arise %s' % (str(e))
                            statsd_client.incr('netflow.stats,result=exception,action=iplookup')
                            print 'netflow_timestamp_received %s, netflow_host %s, ipv4_dst_addr: %s, peer_hash_id: %s' %  (netflow_timestamp_received,netflow_host, ipv4_dst_addr, peer_hash_id)
                            pprint(get_peer_lookup_resp)
                            exit(0) #
            
                # In case of static/install routes define a fuction that given the dest ip address and the initial router (with install) return the exit point, it must support recursion until
                # NH = his own router
            else:
                print 'No bgp peer session found from this netflow host %s' % (netflow_host)


#def internal_stats_publisher():
#    global rib
#    global bgp_stats    
#    while True:
#        print "rib:"
#        pprint(rib)
#        print "bgp_stats:"
#        pprint(bgp_stats)
#        time.sleep(10) 
###   each X sec it read internat stats and send meassurements to telegraf (statsd)
#
##threads = [threading.Thread(target=netflow_consumer), threading.Thread(target=bgp_consumer), threading.Thread(target=internal_stats_publisher)]
#threads = [threading.Thread(target=bgp_consumer), threading.Thread(target=internal_stats_publisher)]

#for t in threads:
#    t.daemon = True    
#    t.start()
#for t in threads:
#    t.join()
get_peer_hash_ids()
netflow_consumer()/data # 
