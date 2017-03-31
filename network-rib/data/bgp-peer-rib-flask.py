#!flask/bin/python
from flask import Flask, jsonify
import pytricia
app = Flask(__name__)

bgp_peer_ribs = {}
bgp_peer_ribs['1.1.1.1'] = pytricia.PyTricia()
bgp_peer_ribs['1.1.1.1']["10.0.0.0/8"] = 'a'
bgp_peer_ribs['1.1.1.1']["10.0.1.0/24"] = 'b'
bgp_peer_ribs['1.1.1.1']["10.0.2.0/24"] = 'c'
bgp_peer_ribs['1.1.1.1']["10.0.0.0/23"] = 'summary'
bgp_peer_ribs['2.2.2.2'] = pytricia.PyTricia()
bgp_peer_ribs['2.2.2.2']["20.0.0.0/8"] = 'a'
bgp_peer_ribs['2.2.2.2']["20.0.1.0/24"] = 'b'
bgp_peer_ribs['2.2.2.2']["20.0.2.0/24"] = 'c'
bgp_peer_ribs['2.2.2.2']["20.0.0.0/23"] = 'summary'
total_requests = 0

@app.route('/bgp_peer_ip_rib/api/v1.0/stats')
def stats():
    global bgp_peer_ribs
    global total_requests
    total_requests += 1
    data = {
        'total_peers'  : len(bgp_peer_ribs),
        'total_requests' : total_requests
    }
    return jsonify(data)

@app.route('/bgp_peer_ip_rib/api/v1.0/ip_lookup/<bgp_peer>/<prefix>',methods=['GET'])
def ip_lookup(bgp_peer,prefix):
    global bgp_peer_ribs
    global total_requests
    total_requests += 1
    # we need to do some validate
    data = { 'result' : bgp_peer_ribs[str(bgp_peer)][str(prefix)] }
    return jsonify(data)

@app.route('/bgp_peer_ip_rib/api/v1.0/add_peer/<bgp_peer>',methods=['POST'])
def add_peer(bgp_peer,prefix):
    # we need to do some validate
    return jsonify(bgp_peer_ribs[bgp_peer][prefix])

@app.route('/bgp_peer_ip_rib/api/v1.0/remove_peer/<bgp_peer>',methods=['POST'])
def remove_peer(bgp_peer,prefix):
    # we need to do some validate
    return jsonify(bgp_peer_ribs[bgp_peer][prefix])

@app.route('/bgp_peer_ip_rib/api/v1.0/add_peer/<bgp_peer>/<prefix>',methods=['POST'])
def add_prefix(bgp_peer,prefix):
    # we need to do some validate
    return jsonify(bgp_peer_ribs[bgp_peer][prefix])

@app.route('/bgp_peer_ip_rib/api/v1.0/remove_peer/<bgp_peer>/<prefix>',methods=['POST'])
def remove_prefix(bgp_peer,prefix):
    # we need to do some validate
    return jsonify(bgp_peer_ribs[bgp_peer][prefix])

if __name__ == '__main__':
    app.run(debug=True)