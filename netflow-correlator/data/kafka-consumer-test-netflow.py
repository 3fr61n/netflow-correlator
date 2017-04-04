#!/usr/bin/python

import os
import socket
import json
from pprint import pprint

from kafka import KafkaConsumer

topic = os.environ['KAFKA_CONSUMER_TOPIC']
kafka_address = socket.gethostbyname(os.environ['KAFKA_ADDR'])
kafka_port = os.environ['KAFKA_PORT']

consumer = KafkaConsumer(topic, bootstrap_servers=[ kafka_address+':'+kafka_port ],auto_offset_reset='latest')

for message in consumer:
    json_thing = str(message.value.decode('ascii'))
    netflow_samples = json.loads(json_thing)
    pprint(netflow_samples)