#!/bin/ash
/usr/bin/envsubst < /data/nfacctd.tmpl > /data/nfacctd.cfg
supervisorctl start nfacctd
#while true; do echo "bla"; sleep 1; done



