#!/bin/ash
# We need to check BMP DB and BMP REST API is up before running this service
while true; do echo "bla"; sleep 1; done
echo "Executing 'python /data/igp_resolver.py'"
python /data/igp_resolver.py
sleep(2)
echo "Executing 'python /data/lsp-install-collector.py'"
python /data/lsp-install-collector.py
sleep(2)
echo "Executing 'python /data/network-rib-to-file.py'"
python /data/network-rib-to-file.py
sleep(2)
supervisorctl start network-rib
#while true; do echo "bla"; sleep 1; done
#gunicorn -b 0.0.0.0:4000 bgp-peer-rib:api --reload
