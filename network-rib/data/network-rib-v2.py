#!usr/bin/python
from __future__ import division
#from flask import Flask, jsonify
import pytricia
from netaddr import valid_ipv4
import os
import socket
import time
import requests
from requests.auth import HTTPBasicAuth
from pprint import pprint
import logging
import logging.handlers
import sys
import yaml
import copy
import json
import pymysql
import time
import statsd

#app = Flask(__name__)

ribs = {}
pnhs = {}
status = {}
peer_hash_ids = {}
bgp_rib_mapping = {}

recursion_depth_max = 15

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR_INPUT = '/data/'
RIBS_FILENAME = 'ribs.yaml'
PNHS_FILENAME = 'pnhs.yaml'
BGP_RIB_MAPPING_FILENAME = 'bgp_rib_mapping.yaml'
#REST_API_PORT = int(os.environ['NETWORK_RIB_REST_PORT'])
#path_analysis = os.environ['PATH_ANALYSIS']
path_analysis = True
#statsd_metrics = os.environ['STATSD_METRICS']
statsd_address = os.environ['STATSD_HOST']
statsd_port = os.environ['STATSD_PORT']
statsd_client = statsd.StatsClient(statsd_address, statsd_port)

#NETFLOW_DB_HOST = os.environ['NETFLOW_DB_HOST']
#NETFLOW_DB_USER = os.environ['NETFLOW_DB_USER']
#NETFLOW_DB_PASSWORD = os.environ['NETFLOW_DB_PASSWORD']
#NETFLOW_DB = os.environ['NETFLOW_DB']

NETFLOW_DB_HOST = 'netflow-collector_1'
NETFLOW_DB_USER = 'juniper'
NETFLOW_DB_PASSWORD = 'juniper123'
NETFLOW_DB = 'pmacct'

NETFLOW_DB_CONFIG = {
  'user': NETFLOW_DB_USER,
  'password': NETFLOW_DB_PASSWORD,
  'host': NETFLOW_DB_HOST,
  'database': NETFLOW_DB,
}

#@app.route('/network-rib/api/v1.0/status')
def status(rest_api=True):
#   It would be nice to ask the rest api about what is he doing, however if we
# are single thread/single core, I thing it would be as useful as I would like to be
    global status
    data = {}
    #peer_hash_ids = get_peer_hash_ids()
    data['result'] = status
    if rest_api:
        return jsonify(data)
    else:
        return data

#@app.route('/network-rib/api/v1.0/update_ribs/',methods=['GET'])
def update_ribs(rest_api=True):
    global ribs

    ribs_tmp = {}
    ribs_yaml = {}
    ribs_yaml_file = BASE_DIR_INPUT + RIBS_FILENAME
    with open(ribs_yaml_file) as f:
        try:
            ribs_yaml = yaml.load(f)
        except Exception, e:
            logger.error('Error importing ribs file: %s', ribs_yaml_file)
            logging.exception(e)
            sys.exit(0)        

    for peer in ribs_yaml.keys():
        logger.debug('Start to populate pytricia object for peer %s', peer) 
        ribs[peer] = pytricia.PyTricia()
        for prefix, pnhs in ribs_yaml[peer].items():
            ribs[peer][prefix] = pnhs
            logger.debug('Adding entry on peer %s for prefix %s with pnh %s', peer, prefix, pnhs) 

    data = {}
    data['result'] = 'Successful ribs load from ' + str(len(ribs)) + ' peers'
    if rest_api:
        return jsonify(data)
    else:
        return data

#@app.route('/network-rib/api/v1.0/update_pnhs/',methods=['GET'])
def update_pnhs(rest_api=True):
    global pnhs

    pnhs_yaml = {}
    pnhs_yaml_file = BASE_DIR_INPUT + PNHS_FILENAME
    with open(pnhs_yaml_file) as f:
        try:
            #pnhs_yaml = yaml.load(f)
            pnhs = yaml.load(f)
        except Exception, e:
            logger.error('Error importing pnhs file: %s', pnhs_yaml_file)
            logging.exception(e)
            sys.exit(0)        

    data = {}
    data['result'] = 'Successful pnhs load from ' + str(len(pnhs)) + ' peers'
    if rest_api:
        return jsonify(data)
    else:
        return data

#@app.route('/network-rib/api/v1.0/update_bgp_mapping/',methods=['GET'])
def update_bgp_mapping(rest_api=True):
    global bgp_rib_mapping

    bgp_rib_mapping_yaml = {}
    bgp_rib_mapping_yaml_file = BASE_DIR_INPUT + BGP_RIB_MAPPING_FILENAME
    with open(bgp_rib_mapping_yaml_file) as f:
        try:
            bgp_rib_mapping = yaml.load(f)
        except Exception, e:
            logger.error('Error importing pnhs file: %s', bgp_rib_mapping_yaml_file)
            logging.exception(e)
            sys.exit(0)        

    data = {}
    data['result'] = 'Successful bgp rib mapping load from ' + str(len(bgp_rib_mapping)) + ' peers'
    if rest_api:
        return jsonify(data)
    else:
        return data

#@app.route('/network-rib/api/v1.0/rib_lookup/<peer_tmp>/<prefix_tmp>',methods=['GET'])
def rib_lookup(peer_tmp,prefix_tmp,rest_api=True):
    # This function will be used to calculate the theorical matrix
    global ribs
    global pnhs
    global bgp_rib_mapping
    peer = str(peer_tmp)   
    prefix = str(prefix_tmp)

    data = {}
    if valid_ipv4(peer):
        #data['result'] = 'Its a valid IP addres %s' % (peer)
        if bgp_rib_mapping.has_key(peer):

            mapped_bgp_rib_peer = bgp_rib_mapping[peer]
            if ribs.has_key(mapped_bgp_rib_peer):
                #data['result'] = 'We have a rib for that peer %s' % (peer)
                if True:
                #if valid_ipv4(prefix):
                    #data['result'] = 'We have valid prefix  %s' % (peer)
                    try:
                        rib_tmp = ribs[mapped_bgp_rib_peer]
                        pnh = rib_tmp[prefix]
                        data['pnh'] = pnh['pnh']
                        data['nhs'] = pnhs[peer][pnh['pnh']]
                    except KeyError, e:
                        data['result'] = 'Prefix %s not found on %s' % (prefix,mapped_bgp_rib_peer)
                    except Exception, e:
                        logging.exception(e)
                        pass 
                else:
                    data['error'] = 'Not a valid IP addres for peer: %s' % (prefix)
            else:
                data['error'] = 'There is no rib related to the mapped bgp peer: %s' % (mapped_bgp_rib_peer)
        else:
            data['error'] = 'There is no bgp rib mapping for that peer: %s' % (peer)
    else:
        data['error'] = 'Not a valid IP addres for peer: %s' % (peer)        

    if rest_api:
        return jsonify(data)
    else:
        return data


def flattern(A):
    rt = []
    for i in A:
        if isinstance(i,list): rt.extend(flattern(i))
        else: rt.append(i)
    return rt

def analyze_path(**kwargs):
    global logger
    global ribs
    global pnhs

    source_router=kwargs['source_router']
    source_router=source_router.strip()
    ipv4_dst_addr=kwargs['ipv4_dst_addr']
    ipv4_dst_addr=ipv4_dst_addr.strip()
    intermediate_router=kwargs['intermediate_router']
    intermediate_router=intermediate_router.strip()
    weight = kwargs['weight']
    recursion_depth=kwargs['recursion_depth']
    logger.info('Analyzing path from router %s to destination address %s and weight %s - iteration (%s)', intermediate_router,ipv4_dst_addr,weight,recursion_depth)

    try:
        mapped_bgp_rib_peer = bgp_rib_mapping[intermediate_router]
    except Exception, e:
        logger.error('There is not mapping bgp rib for peer: %s', intermediate_router)
        result = {}
        result['endpoint'] = intermediate_router
        result['weight'] = weight
        result['status'] = 'There is not mapping bgp rib for this peer'
        return result

    my_pnhs = ribs[mapped_bgp_rib_peer][ipv4_dst_addr]
    weight_per_pnh = weight / len(my_pnhs)
    logger.debug('Calculating weight %s / len(my_pnhs) %s  =   weight_per_pnh %s', weight,len(my_pnhs),weight_per_pnh)
    
    for dummy, my_pnh in my_pnhs.items():
        if recursion_depth > recursion_depth_max:
            # Recursion depth is too high, we should STOP and notify, about a possible loop or a very long path
            raise ValueError('Max recursion depth reached, warning possible network loop at %s' % intermediate_router)
        elif my_pnh == intermediate_router:
            # Final destination reached (pnh is the intermediate_router, that router is announcing that prefix)
            result = {}
            result['endpoint'] = intermediate_router
            result['weight'] = weight_per_pnh
            result['status'] = 'recursion_ended'
            return [ result ]     
        else:
            #if intermediate_router == source_router:  # first hop analysis
            nhs = pnhs[intermediate_router][my_pnh]
            weight_per_nh = weight_per_pnh / len(nhs)
            logger.debug('Calculating weight_per_pnh %s / len(nhs) %s  =   weight_per_nh %s', weight_per_pnh,len(nhs),weight_per_nh)

            recursion_depth = recursion_depth + 1
            my_result = []
            for nh in nhs:
                endpoint = nh['endpoint']
                weight_per_nh_tmp = weight_per_nh  
                result_tmp = analyze_path(source_router=source_router,ipv4_dst_addr=ipv4_dst_addr,intermediate_router=endpoint,weight=weight_per_nh_tmp,recursion_depth=recursion_depth)
                my_result.append(result_tmp)

            result = flattern(my_result)
            return result
 
#@app.route('/network-rib/api/v1.0/analyze_path/<peer_id>/<prefix>',methods=['GET'])
def analyze_path_tmp(peer_id,prefix,rest_api=True):
    global logger
    global ribs
    global pnhs
    initial_weight = 1
    recursion_depth = 1
    source_router = str(peer_id)
    ipv4_dst_addr = str(prefix)
    data = {}

    if valid_ipv4(source_router):
        #data['result'] = 'Its a valid IP addres %s' % (peer)  
        if bgp_rib_mapping.has_key(source_router):
            mapped_bgp_rib_peer = bgp_rib_mapping[source_router]
            if ribs.has_key(mapped_bgp_rib_peer):
                #data['result'] = 'We have a rib for that peer %s' % (peer)
                if True:
                #if valid_ipv4(ipv4_dst_addr):
                    logger.info('Start analyzing path from router %s to destination address %s', source_router,ipv4_dst_addr)
                    try:
                        data['result'] = analyze_path(source_router=source_router,ipv4_dst_addr=ipv4_dst_addr,intermediate_router=source_router,weight=initial_weight,recursion_depth=recursion_depth)
                    except ValueError as err:
                        data['error'] = err.args
                else:
                    data['error'] = 'Not a valid IP addres for peer: %s' % (prefix)
            else:
                data['error'] = 'There is no rib related to bgp mapped peer: %s' % (mapped_bgp_rib_peer)
        else:
            data['error'] = 'There is no bgp rib mapping for that peer: %s' % (peer)   
    else:
        data['error'] = 'Not a valid IP addres for peer: %s' % (peer)  

    if rest_api:
        return jsonify(data)
    else:
        return data


def get_tables (**kwargs):
    
    conn=kwargs['conn']
    tables=[]
    query = "SHOW TABLES LIKE 'tm%';"
    cursor = conn.cursor()
    cursor.execute(query)
    for (table_name,) in cursor:
        tables.append(table_name)
    return tables

def analyze_netflow_samples (**kwargs):
    conn=kwargs['conn']
    table=kwargs['table']
    max_rows_to_fetch = 1000
    query = 'SELECT * FROM %s;' % table
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchmany(size=max_rows_to_fetch)
    while rows:
        for row in rows:

#        peer_ip_src char(15) default '0.0.0.0', 
#        net_src char(15) default '0.0.0.0',
#        mask_src varchar(5) default '/0', 
#        net_dst char(15) default '0.0.0.0',
#        mask_dst varchar(5) default '/0', 
#        packets int (10) unsigned,
#        bytes bigint(20) unsigned, 
#        sampling_rate int(6) unsigned,
#        stamp_inserted datetime,
#        stamp_updated datetime,


            peer_ip_src = row[0]
#            ip_src = row[2]
            net_src = row[1]
            mask_src = row[2]
#            ip_dst = row[5]
            net_dst = row[3]
            mask_dst = row[4]
            packets = row[5]
            bytes = row[6]
            sampling_rate = row[7]
            stamp_inserted = row[8]
            stamp_updated = row[9]
            prefix_src = net_src + '/' + mask_src
            prefix_dst = net_dst + '/' + mask_dst

            packets_sent = packets * sampling_rate
            bytes_sent = bytes * sampling_rate

            rib_lookup_resp = rib_lookup(peer_tmp=peer_ip_src ,prefix_tmp=prefix_dst,rest_api=False)
            #pprint(rib_lookup_resp)
            if rib_lookup_resp.has_key('pnh'):
                bgp_next_hop = rib_lookup_resp['pnh']
                statsd_client.incr('netflow.stats,result=succeed,action=iplookup')
                statsd_client.incr('netflow.theorical_matrix_bytes,src_PE='+peer_ip_src+',dst_PE='+bgp_next_hop,count=bytes_sent)
                statsd_client.incr('netflow.theorical_matrix_packets,src_PE='+peer_ip_src+',dst_PE='+bgp_next_hop,count=packets_sent)   
#                statsd_client.incr('netflow.theorical_matrix_bytes,src_PE='+peer_ip_src+',dst_PE='+bgp_next_hop+',tm='+table,count=bytes_sent)
#                statsd_client.incr('netflow.theorical_matrix_packets,src_PE='+peer_ip_src+',dst_PE='+bgp_next_hop+',tm='+table,count=packets_sent)   
                logger.info('netflow.theorical_matrix_packets,src_PE=%s,dst_PE=%s,prefix=%s,tm=%s,count=%s' %  (peer_ip_src,bgp_next_hop,prefix_dst,table,packets_sent))
                if path_analysis:
                    path_analysis_resp=analyze_path_tmp(peer_id=peer_ip_src,prefix=prefix_dst,rest_api=False)
                    #pprint(rib_lookup_resp)
                    if path_analysis_resp.has_key('error'):
                        logger.error('Error message returned:  %s' % (path_analysis_resp['error']))
                        statsd_client.incr('netflow.stats,result=error,action=analyze_path')
                    elif path_analysis_resp.has_key('result'):
                        endpoints = path_analysis_resp['result']
                        for endpoint in endpoints:
                            weighted_bytes_sent = packets_sent * endpoint['weight']
                            weighted_packets_sent = packets_sent * endpoint['weight']
                            dst_PE = endpoint['endpoint']
                            logger.info('netflow.real_matrix_packets,src_PE=%s,dst_PE=%s,prefix=%s,tm=%s,count=%s,fraction=%s' %  (peer_ip_src,dst_PE,prefix_dst,table,weighted_packets_sent,endpoint['weight']))
                            statsd_client.incr('netflow.real_matrix_bytes,src_PE='+peer_ip_src+',dst_PE='+dst_PE,count=weighted_bytes_sent)   
                            statsd_client.incr('netflow.real_matrix_packets,src_PE='+peer_ip_src+',dst_PE='+dst_PE,count=weighted_packets_sent)   
#                            statsd_client.incr('netflow.real_matrix_bytes,src_PE='+peer_ip_src+',dst_PE='+dst_PE+',tm='+table,count=weighted_bytes_sent)   
#                            statsd_client.incr('netflow.real_matrix_packets,src_PE='+peer_ip_src+',dst_PE='+dst_PE+',tm='+table,count=weighted_packets_sent)   


        rows = cursor.fetchmany(size=max_rows_to_fetch)
    cursor.close()


if __name__ == '__main__':
    update_ribs(rest_api=False)
    update_pnhs(rest_api=False)
    update_bgp_mapping(rest_api=False)

    last_table_read = ""
    while True:
        try:
            logger.info('Connecting to database %s in server %s', NETFLOW_DB,NETFLOW_DB_HOST)
            myConnection = pymysql.connect( **NETFLOW_DB_CONFIG )
            # Get all tables with netflow data
            logger.info('Extracting tables with netflow samples tables on server %s',NETFLOW_DB_HOST)
            tables = get_tables (conn=myConnection)
#            last_table_read_index = tables.index(last_table_read) if last_table_read in tables else 0       
#            if len(tables[last_table_read_index:-1]) > 1:
#                for table in tables[last_table_read_index:-1]:
            if ((len(tables) > 1) and (last_table_read != tables[-2])):
                table = tables[-2]
                logger.info('Processing netflow samples from table %s in server %s',table,NETFLOW_DB_HOST)
                analyze_netflow_samples(conn=myConnection,table=table)
                last_table_read = table
            else:
                logger.info('All available tables were already processed on %s, so nothing to do, waiting for new tables',NETFLOW_DB_HOST)
            # We should delete old tables
    
        except Exception, e:
            logger.error('Got error {!r}, errno is {}'.format(e, e.args[0]))
            logging.exception(e)
            # This timer should be tunned
            pass            
        logger.info('Sleeping until next round')
        time.sleep(300)
            
    # Start loops each 5 min
        # Check if netflow database is up and running

        # If database is OK then get the penultimate table (just 5 min ago)
        # Perform query SELECT * FROM <penuntimate_table>
        # get rows un chunk mode (scaling)
        # copy code from netflow-correlator
        # for each row
            # get flow info source_PE,  src_net, dst_net
            # find for known flow in flow cache (TBD)
            # if flow not found 
                #do ip lookup and save theorical matrix\
                # do path analyais and save real matrix
        #sleep (?)

        #keep last 12 tables
