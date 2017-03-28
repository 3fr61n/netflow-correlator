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

lock = threading.Lock() 
rib = {}

def netflow_consumer():
#   It read netflow bgp topics query the BGP RIB structure, send result to telegraf and update netflow stats
#    bgp_topic = os.environ['NETFLOW_KAFKA_TOPIC']
#    kafka_address = socket.gethostbyname(os.environ['KAFKA_ADDR'])
#    kafka_port = os.environ['KAFKA_PORT']
#    global rib
#    global bgp_stats


#{u'dst_as': 12956,
# u'dst_mask': 32,
# u'engine_id': 0,
# u'engine_type': 0,
# u'first_switched': u'2017-03-17T16:21:55.999Z',
# u'flow_records': 13,
# u'flow_seq_num': 4088805,
# u'host': u'192.168.255.1',
# u'in_bytes': 910,
# u'in_pkts': 13,
# u'input_snmp': 550,
# u'ipv4_dst_addr': u'224.0.0.2',
# u'ipv4_next_hop': u'0.0.0.0',
# u'ipv4_src_addr': u'10.10.10.2',
# u'l4_dst_port': 646,
# u'l4_src_port': 646,
# u'last_switched': u'2017-03-17T16:22:48.999Z',
# u'output_snmp': 0,
# u'protocol': 17,
# u'sampling_algorithm': 0,
# u'sampling_interval': 1,
# u'src_as': 12956,
# u'src_mask': 30,
# u'src_tos': 192,
# u'tcp_flags': 0,
# u'timestamp': u'2017-03-17T16:22:51.000Z',
# u'version': 5}

    bgp_topic = 'netflow'
    kafka_address = 'kafka'
    kafka_port = '9092'
    openbmp_rest_address = 'mysql'
    openbmp_rest_port = '8001'
    openbmp_rest_user = "openbmp"
    openbmp_rest_password = "CiscoRA"

    consumer = KafkaConsumer(bgp_topic, bootstrap_servers=[ kafka_address+':'+kafka_port ], auto_offset_reset='latest')

    for message in consumer:
        # message value and key are raw bytes -- decode if necessary!
        # e.g., for unicode: `message.value.decode('utf-8')`
        json_thing = str(message.value.decode('ascii'))
        netflow_sample = json.loads(json_thing)

#        pprint(netflow_sample)
        netflow_host = netflow_sample['host']
        ipv4_dst_addr = netflow_sample['ipv4_dst_addr']
        netflow_timestamp_received = netflow_sample['timestamp']


        get_peer_url = 'http://'+openbmp_rest_address+':'+openbmp_rest_port+'/db_rest/v1/peer/remoteip/'+netflow_host
        print get_peer_url
        openbmp_rest_auth=HTTPBasicAuth(openbmp_rest_user, openbmp_rest_password)

        resp = requests.get(get_peer_url, auth=openbmp_rest_auth)
        if resp.status_code != 200:
            # This means something went wrong.
            raise ApiError('GET /tasks/ {}'.format(resp.status_code))
        else:
            get_peer_resp = resp.json()
            peer_hash_id = ""
            if get_peer_resp['v_peers']['size'] == 0:
                print("There is no bgp session with that IP")
            else:
                peer_hash_id = get_peer_resp['v_peers']['data'][0]['peer_hash_id']
                print 'netflow_timestamp_received %s, netflow_host %s, ipv4_dst_addr: %s, peer_hash_id: %s' %  (netflow_timestamp_received,netflow_host, ipv4_dst_addr, peer_hash_id)
                #pprint (get_peer_resp)
                get_peer_lookup_url = 'http://'+openbmp_rest_address+':'+openbmp_rest_port+'/db_rest/v1/rib/peer/'+peer_hash_id+'/lookup/'+ipv4_dst_addr
                #http://172.30.121.19:8001/db_rest/v1/rib/peer/4d2a478db51525ee9ffcef8483a1e0fd/lookup/20.0.12.81
                resp = requests.get(get_peer_lookup_url, auth=openbmp_rest_auth)
                if resp.status_code != 200:
                    # This means something went wrong.
                    raise ApiError('GET /tasks/ {}'.format(resp.status_code))
                else:            
                    get_peer_lookup_resp = resp.json()
                    pprint (get_peer_lookup_resp)

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
netflow_consumer()/data # 

