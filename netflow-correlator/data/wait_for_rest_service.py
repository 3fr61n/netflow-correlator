import os
import socket
import json
import time
import requests
from pprint import pprint
from requests.auth import HTTPBasicAuth

openbmp_rest_address = socket.gethostbyname(os.environ['OPENBMP_REST_ADDR'])
openbmp_rest_port = os.environ['OPENBMP_REST_PORT']
openbmp_rest_user = os.environ['OPENBMP_REST_USER']
openbmp_rest_password = os.environ['OPENBMP_REST_PASSWORD']
openbmp_rest_auth=HTTPBasicAuth(openbmp_rest_user, openbmp_rest_password)
rest_api_base_url='http://'+openbmp_rest_address+':'+openbmp_rest_port

rest_status = False

def check_rest_status():
    # Check if rest api server (bmp db) is alive 

    get_peer_url = rest_api_base_url+'/db_rest/v1/peer'

    
    try:
        resp = requests.get(get_peer_url, auth=openbmp_rest_auth)
        if resp.status_code != 200:
            # This means something went wrong.
            print "Rest server answer:"
            print 'GET /tasks/ {}'.format(resp.status_code)
            return False
        else:
            get_peer_resp = resp.json()
            pprint (get_peer_resp)
            if get_peer_resp['v_peers']['size'] == 0:
                print("No bgp peers found")  
                # although the server seems to be up, if there is no peers we could not do anything yet
                return False
            else:
                print("Rest server status is ok, and there is bgp peers alive")  
                # although the server seems to be up, if there is no peers we could not do anything yet
                return True
    except Exception, e:
        print 'This exception arise %s' % (str(e))
        return False

while rest_status == False:
    rest_status = check_rest_status()
    time.sleep(5)