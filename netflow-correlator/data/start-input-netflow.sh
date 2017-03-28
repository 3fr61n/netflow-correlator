#!/bin/ash
python /data/wait_for_rest_service.py
supervisorctl start nfacctd
#while true; do echo "bla"; sleep 1; done
