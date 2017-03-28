#!/usr/bin/python

import os
import socket
import json
from pprint import pprint

from kafka import KafkaConsumer

bgp_topic = os.environ['BGP_KAFKA_TOPIC']
kafka_address = socket.gethostbyname(os.environ['KAFKA_ADDR'])
kafka_port = os.environ['KAFKA_PORT']

consumer = KafkaConsumer(bgp_topic, bootstrap_servers=[ kafka_address+':'+kafka_port ])

for message in consumer:
    # message value and key are raw bytes -- decode if necessary!
    # e.g., for unicode: `message.value.decode('utf-8')`
    json_thing = str(message.value.decode('ascii'))
    if type(json_thing) is str:
        print(json.dumps(json.loads(json_thing), sort_keys=True, indent=4))
    else:
        print(json.dumps(json_thing, sort_keys=True, indent=4))

#    print ("%s:%d:%d: key=%s value=%s" % (message.topic, message.partition,
#                                          message.offset, message.key,
#                                          message.value))

