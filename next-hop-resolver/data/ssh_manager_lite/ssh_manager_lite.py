#!/usr/bin/env python
# coding: utf-8
# Author: psagrera@juniper.net
# Version: 1.0 20150928 

__author__ = """ Pablo Sagrera(psagrera@juniper.net) """


import yaml
import sys
import os
import pprint
import argparse 
import time
import logging
import logging.handlers
import pxssh
import logging
import re
from time import sleep 
import signal, fcntl, termios, struct

try:
	import pexpect
except:
	raise

sys.tracebacklimit=0
global_pexpect_instance = None # Used by signal handler

# These variables are set to get rid of winsize issues in interactive mode
os.environ['LINES'] = "50"
os.environ['COLUMNS'] = "160"


##################################################
##################################################
# Defining the class and functions 
##################################################
##################################################
class timeout_exception(pexpect.TIMEOUT):
	
	'''
	 session timed out trying to connect to the device
	'''    
	pass

class ssh_manager_lite (object):
	

	# -----------------------------------------------------------------------
	# CONSTRUCTOR
	# -----------------------------------------------------------------------

	def __init__(self,**kvargs):

		
		# Setting BASE directory
		if getattr(sys, 'frozen', False):
			# frozen
			BASE_DIR = os.path.dirname(sys.executable)
		else:
			# unfrozen
			BASE_DIR = os.path.dirname(os.path.realpath(__file__))
		
		# Loading default variables file

		default_variables_yaml_file = BASE_DIR + "/data/ssh_manager_lite.variables.yaml"
		default_variables = {}

		with open (default_variables_yaml_file) as df:
			default_variables = yaml.load(df)
		
		# Setting credential file
		credentials_yaml_file = BASE_DIR + '/' +  default_variables['data_dir'] + '/profiles.yaml'
		targets_yaml_file = BASE_DIR + '/' + default_variables['data_dir'] + '/targets.yaml'

		# defining dictionaries 
		credentials = {}
		gateways = {}
		targets = {}

		# Loading both gateways and credentials 
		with open(credentials_yaml_file) as f: 
			self.credentials,self.gateways = yaml.load_all(f)    
		
		# Loading hosts file
		with open(targets_yaml_file) as h:
			self.targets = yaml.load(h)

		# Getting target
		self._target = kvargs['target']
		
		if self._target not in self.targets.keys():
			raise Exception ("target %s not found" %self._target)
			sys.exit(1)
		else:				
			self.profile = self.targets[self._target]

	# -----------------------------------------------------------------------
	# OVERLOADS
	# -----------------------------------------------------------------------  

	def __repr__ (self):

		return "Device(%s,%s)" %(self.profile,self._target)

	# -----------------------------------------------------------------------
	# FUNCTIONS START HERE
	# -----------------------------------------------------------------------
	
	def _get_profile(self,profile):
		
		"""
			Functions that retrieves profiles (credentials and gateways) 
		"""
		# Some auxiliary variables
		
		gtws = {}
		cred = {}
		gt = {}
		
		startup_commands = []
		target_credentials = []
		gateway = []
		
		
		try:
			if 'startup_commands' in self.credentials['profiles'][profile].keys():
				startup_commands = self.credentials['profiles'][profile]['startup_commands']
		except KeyError as k:
			print "Error getting key: %s" %k
			sys.exit(1)	
		try:
			if 'gateway_list' in self.credentials['profiles'][profile].keys():
				gateway = self.credentials['profiles'][profile]['gateway_list']
		except KeyError as k:
			print "Error getting key: %s" %k
			sys.exit(1)
		
		if isinstance(gateway,list):		
			# We have 0 or more jump host		
			gtws = {key:value for (key,value) in self.gateways.iteritems()}
			cred = {key:value for (key,value) in self.credentials.iteritems()}

			for i in gateway:
				if i in gtws['gateways']:
					gt[i] = gtws['gateways'][i]		
			if startup_commands is not None:
				target_credentials = [gateway,gt,cred['profiles'][profile],startup_commands] 	
			else:
				target_credentials = [gateway,gt,cred['profiles'][profile]]	

		pprint.pprint (target_credentials)
		return sorted(target_credentials)

	def open (self,interactive=False):

		"""
			Open connection to remote host via jump host (or directly)
			An interactive mode is possible setting interactive variable to True
		"""		
		
		# Loading credential values
		credential_values = self._get_profile(self.profile)
		
		cmd_result = ''
		expct_sequence = []
		global global_pexpect_instance
		
		#######################################################################
		# Asigning variables (startup commands and gateway_list are optional) #
		#######################################################################
		
		# Try to change this Anti-pattern by a,b,c = credential_values model	

		# No gateways and startup command 
		if not credential_values[0]:
			expct_sequence = credential_values[1]
			final_target = credential_values[2]

		# One gateway and startup commands 
		elif len(credential_values[2]['gateway_list'])==1:
			expct_sequence = credential_values[1]
			final_target = credential_values[2]
			gateway_information =credential_values[0]
		
		# More than one gateway and startup commands
		elif len(credential_values[2]['gateway_list'])>1:
			expct_sequence = credential_values[0]
			final_target = credential_values[2]
			gateway_information =credential_values[1]		
		
		else:
			final_target = credential_values[0]
			gateway_information =credential_values[1]
		# At least one jump host
		if 'gateway_list' in final_target.keys():
			if isinstance(final_target['gateway_list'],list):
				iterator = 0
				max_gateways =  len(gateway_information)
				for k,v in sorted(gateway_information.iteritems()):
					print gateway_information[k]['connection_mode']
					if re.search('ssh', gateway_information[k]['connection_mode'],re.IGNORECASE):
						if iterator == 0:
							conn = pexpect.spawn(gateway_information[k]['connection_mode'] + ' -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no '+' %s@%s' %(gateway_information[k]['username'],gateway_information[k]['ip_address']),timeout = 10)
							iterator += 1
						else:
							conn.sendline(gateway_information[k]['connection_mode'] + ' -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no '+' %s@%s' %(gateway_information[k]['username'],gateway_information[k]['ip_address']))
					
					elif re.search('telnet', gateway_information[k]['connection_mode'],re.IGNORECASE):
						if iterator == 0:
							conn = pexpect.spawn(gateway_information[k]['connection_mode'] +' -l %s %s %s' %(gateway_information[k]['username'],gateway_information[k]['ip_address'],gateway_information[k]['port']),timeout = 10)
							iterator += 1
						else:
							conn.sendline(gateway_information[k]['connection_mode'] +' -l %s %s %s' %(gateway_information[k]['username'],gateway_information[k]['ip_address'],gateway_information[k]['port']))
					else:
						print "Connection mode not supported %s" %gateway_information[k]['connection_mode']
						sys.exit(1)
					jump_host_conn = conn.expect ([pexpect.TIMEOUT,'[Pp]assword:'])
					print jump_host_conn
					if jump_host_conn == 0:
						conn.logfile = sys.stdout
						print 'ERROR! could not login with SSH. Here is what SSH said: %s' %conn.after
						self.close(conn)
						sys.exit (1)
					else:
						conn.sendline (gateway_information[k]['password'])
						conn.expect (gateway_information[k]['pri_prompt'])
	
				sleep(2)
				
				if re.search('ssh',final_target['connection_mode'],re.IGNORECASE):
					conn.sendline (final_target['connection_mode'] + ' -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no '+'%s@%s' %(final_target['username'],self._target))
				elif re.search('telnet',final_target['connection_mode'],re.IGNORECASE):
					conn.sendline (final_target['connection_mode'] +' -l %s %s' %(final_target['username'],self._target),timeout = 10)
				else:
					print "Connection mode not supported %s" % final_target['connection_mode']
					sys.exit(1)
				hw_conn = conn.expect([pexpect.TIMEOUT,'[Pp]assword:'])
				if hw_conn == 0:
					msg = 'ERROR! could not login with SSH. Here is what SSH said: %s' %conn.after
					raise timeout_exception(msg)
				else:
					print self
					conn.sendline(final_target['password'])
					conn.expect(final_target['pri_prompt'])
					# Start the interactive session
					if interactive:
						print ("Starting interactive session,please Type ^] to escape from the script \n")
						# Setting startup commands for interactive session
						for j in expct_sequence['interactive']:
							if isinstance(j,dict):
								conn.sendline(j['send'])
								conn.expect(j['expct'])
						global_pexpect_instance = conn
						signal.signal(signal.SIGWINCH, self.sigwinch_passthrough)

						conn.sendline('')
						conn.interact(chr(29))
						print "Escape sequence detected... exiting"
					else:
						# Setting startup commands for non-interactive session
						for j in expct_sequence['non_interactive']:
							if isinstance(j,dict):
								conn.sendline(j['send'])
								conn.expect(j['expct'])
		# No gateways
		else:
			if re.search('ssh',final_target['connection_mode'],re.IGNORECASE):
				conn = pexpect.spawn(final_target['connection_mode'] + ' -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no '  +' %s@%s' %(final_target['username'],self._target),timeout = 30)
			elif re.search('telnet',final_target['connection_mode'],re.IGNORECASE):
				conn = pexpect.spawn(final_target['connection_mode'] +' -l %s %s' %(final_target['username'],self._target),timeout = 30)
			else:
				print "Connection mode %s not supported" %final_target['connection_mode']
				sys.exit(1)
			final_host_conn = conn.expect ([pexpect.TIMEOUT,'[Pp]assword:'])
			
			if final_host_conn == 0:
				print 'ERROR! could not login with SSH. Here is what SSH said:'
				print conn.before, conn.after
				self.close(conn)
				sys.exit(1)
			else:
				print self
				conn.sendline(final_target['password'])
				conn.expect (final_target['pri_prompt'])
				sleep(1)
				# Start the interactive session
				if interactive:
					print ("Starting interactive session,please Type ^] to escape from the script \n")
					# Setting startup commands for interactive session
					for j in  expct_sequence['interactive']:
						if isinstance(j,dict):
							conn.sendline(j['send'])
							conn.expect(j['expct'])
					global_pexpect_instance = conn
					signal.signal(signal.SIGWINCH, self.sigwinch_passthrough)
					conn.sendline('')
					conn.interact(chr(29))
					print "Escape sequence detected... exiting"
				else:
					# Setting startup commands for non-interactive session
					for j in  expct_sequence['non_interactive']:
						if isinstance(j,dict):
							conn.sendline(j['send'])
							conn.expect(j['expct'])
		# Returning class object
		return conn
		
	def command_executor(self,obj,command):

			"""
				This runs a command/s on the remote host
			"""	

			if not getattr(obj,'closed'):
				obj.sendline(command)
				obj.expect(getattr(obj,'after'))
				return self.strip_command(command,obj.before)

	def strip_command (self,command_string,output):

		command_length = len(command_string) + 1 
		return output[command_length:]		

	def sigwinch_passthrough (sig, data):

		# Check for buggy platforms (see pexpect.setwinsize()).
		if 'TIOCGWINSZ' in dir(termios):
			TIOCGWINSZ = termios.TIOCGWINSZ
		else:
			TIOCGWINSZ = 1074295912 # assume
		s = struct.pack ("HHHH", 0, 0, 0, 0)
		a = struct.unpack ('HHHH', fcntl.ioctl(sys.stdout.fileno(), TIOCGWINSZ , s))
		global global_pexpect_instance
		global_pexpect_instance.setwinsize(a[0],a[1])
		
	def close (self,obj):

		"""
			Close pexpect connection
		"""
		return obj.close()



