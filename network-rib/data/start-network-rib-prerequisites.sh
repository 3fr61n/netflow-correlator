#!/bin/bash
#python /data/wait_for_rest_service.py
#We should edit the port to listen
#supervisorctl start nfacctd
while true; do echo "bla"; sleep 1; done
#gunicorn -b 0.0.0.0:4000 bgp-peer-rib:api --reload
