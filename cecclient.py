#! /usr/bin/env python3

# This file is part of the cecdaemon project
#
# Based on the demo of the python-libcec API, some original code left
# For more information about libCEC contact:
# Pulse-Eight Licensing	   <license@pulse-eight.com>
#	 http://www.pulse-eight.com/
#	 http://www.pulse-eight.net/
#
# copyright 2021 Alexandre Foley (alexandre.foley@usherbrooke.ca)
#
# Licensed under the GNU General Public License 
# See LICENSE file in the project root for full license information.

import cec
import inspect
import sys
import functools

# print(cec)


def multidispatch(*types):
	def register(function):
		name = function.__name__
		mm = multidispatch.registry.get(name)
		if mm is None:
			@functools.wraps(function)
			def wrapper(self, *args):
				types = tuple(arg.__class__ for arg in args) 
				function = wrapper.typemap.get(types)
				if function is None:
					raise TypeError("no match")
				return function(self, *args)
			wrapper.typemap = {}
			mm = multidispatch.registry[name] = wrapper
		if types in mm.typemap:
			raise TypeError("duplicate registration")
		mm.typemap[types] = function
		return mm
	return register
multidispatch.registry = {}

def register_mainloop_command(*cmds:str):
	"""Decorator to register a function for the interactive interface. """
	def deco(func):
		func.__cmds__ = cmds
		return func
	return deco


def Interactive_Mode( cls ):
	cls.help_string = "\n"
	for name, func in inspect.getmembers(cls):
		if hasattr(func, '__cmds__'):
			cmdstr = ', '.join(func.__cmds__)
			for cmd in func.__cmds__ :
				cls.interactive_cmd[cmd] = func
			cls.help_string = cls.help_string + '{:<15} {:>0}'.format(cmdstr, func.__doc__ )+ '\n'
	return cls

def str_to_logical_address(log_addr:str):
	try:
		out = int(log_addr)
		if not (out >= cec.CECDEVICE_TV and out <=cec.CECDEVICE_BROADCAST):
			out = cec.CECDEVICE_UNKNOWN
		return out
	except:
		print("logical adress must be a number in the range [{},{}]".format(cec.CECDEVICE_TV,cec.CECDEVICE_BROADCAST),file=self.stdout)

@Interactive_Mode
class pyCecClient:
	cecconfig = cec.libcec_configuration()
	lib = {}
	log_level = cec.CEC_LOG_ALL
	help_string = ""
	interactive_cmd = {}
	stdout = sys.stdout
	stdin = sys.stdin
	
	@register_mainloop_command("h","help")
	def PrintHelpMessage(self):
		"""Print this help message"""
		print(self.help_string,file=self.stdout)

	# create a new libcec_configuration
	def SetConfiguration(self):
		self.cecconfig.strDeviceName = "pyLibCec"
		self.cecconfig.bActivateSource = 0
		self.cecconfig.deviceTypes.Add(cec.CEC_DEVICE_TYPE_RECORDING_DEVICE)
		self.cecconfig.clientVersion = cec.LIBCEC_VERSION_CURRENT

	def SetLogCallback(self, callback):
		self.cecconfig.SetLogCallback(callback)

	def SetKeyPressCallback(self, callback):
		self.cecconfig.SetKeyPressCallback(callback)

	def SetCommandCallback(self, callback):
		self.cecconfig.SetCommandCallback(callback)

	def SetConfigurationChangedCallback(self, callback):
		self.cecconfig.SetConfigurationChangedCallback(callback)
	
	def SetSourceActivatedCallback(self,callback):
		self.cecconfig.SetSourceActivatedCallback(callback)
	
	def SetMenuStateCallback(self,callback):
		self.cecconfig.SetMenuStateCallback(callback)
	
	def SetAlertCallback(self,callback):
		self.cecconfig.SetAlertCallback(callback)

	def DetectAdapter(self):
		""" detect an adapter and return the com port path """
		retval = None
		adapters = self.lib.DetectAdapters()
		for adapter in adapters:
			print("found a CEC adapter:",file=self.stdout)
			print("port:	 " + adapter.strComName,file=self.stdout)
			print("vendor:   " + hex(adapter.iVendorId),file=self.stdout)
			print("product:  " + hex(adapter.iProductId),file=self.stdout)
			retval = adapter.strComName
		return retval

	# initialise libCEC
	def InitLibCec(self):
		self.lib:cec.ICECAdapter = cec.ICECAdapter.Create(self.cecconfig)
		# print libCEC version and compilation information
		print(
			"libCEC version "
			+ self.lib.VersionToString(self.cecconfig.serverVersion)
			+ " loaded: "
			+ self.lib.GetLibInfo()
		)

		# search for adapters
		self.adapter = self.DetectAdapter()
		if self.adapter == None:
			print("No adapters found",file=self.stdout)
		else:
			if self.lib.Open(self.adapter):
				print("connection opened",file=self.stdout)
			else:
				print("failed to open a connection to the CEC adapter",file=self.stdout)

	# display the addresses controlled by libCEC
	@register_mainloop_command('address')
	def ProcessCommandSelf(self):
		"""Display the address controled by libCEC"""
		addresses = self.lib.GetLogicalAddresses()
		strOut = "Addresses controlled by libCEC: "
		x = 0
		notFirst = False
		while x < 15:
			if addresses.IsSet(x):
				if notFirst:
					strOut += ", "
				strOut += self.lib.LogicalAddressToString(x)
				if self.lib.IsActiveSource(x):
					strOut += " (*)"
				notFirst = True
			x += 1
		print(strOut,file=self.stdout)

	# send an active source message
	@register_mainloop_command("be_as")
	def CommandActiveSource(self):
		"""make this CEC device the active source"""
		return self.lib.SetActiveSource()

	@register_mainloop_command("be_is")
	def CommandInactiveSource(self):
		"""Broadcast that this CEC device is no longer the source"""
		return self.lib.SetInactiveView()

	def GetActiveSource(self):
		"""return the logical address of the currently active source"""
		return self.lib.GetActiveSource()

	@register_mainloop_command("sleep_tv")
	def sleep_TV(self):
		"""
		Turn off the TV if this is the active source
		"""
		cur_as = self.GetActiveSource()
		if cur_as <=15 and cur_as >=0:
			if self.lib.GetLogicalAddresses()[cur_as]:
				self.StandbyDevice(0)
				self.CommandInactiveSource()

	def ToggleDevicePower(self,logical_address:int):
		"""toggle the power status of a device"""
		is_on = self.lib.GetDevicePowerStatus(logical_address)
		if is_on == cec.CEC_POWER_STATUS_STANDBY or is_on == cec.CEC_POWER_STATUS_UNKNOWN:
			out = self.PowerOnDevices(logical_address)
			self.CommandActiveSource()
			return out
		if is_on == cec.CEC_POWER_STATUS_ON:
			self.CommandInactiveSource()
			return self.StandbyDevice(logical_address)
		return False

	@register_mainloop_command("toggle_power")
	def ProcessToggleDevicePower(self,logical_address:str):
		"Toggle the power status of the device with the logical address"
		return self.ToggleDevicePower(str_to_logical_address(logical_address))

	@register_mainloop_command("get_as")
	def ProcessGetActiveSource(self):
		"""Obtain the logical address of the active source"""
		print(self.GetActiveSource(),file=self.stdout)

	def StandbyDevice(self,logical_address:int):
		"""
		put the device in standby
		"""
		return self.lib.StandbyDevices(logical_address)
	# send a standby command
	@register_mainloop_command("standby")
	def ProcessCommandStandby(self,logical_address:str):
		"""Send a standby command"""
		if not self.StandbyDevice(str_to_logical_address(logical_address)):
			print("invalid destination",file=self.stdout)

	def SetLogicalAddress(self,logical_address:int):
		"""set logical adress of the CEC device"""
		return self.lib.SetLogicalAddress(logical_address)

	@register_mainloop_command("set_la")
	def ProcessSetLogicalAddress(self,logical_address:str):
		"""set logical adress of the CEC device"""
		if not self.SetLogicalAddress(str_to_logical_address(logical_address)):
			print("command failed",file=self.stdout)

	def SetHDMIPort(self, base_device_logical_address:int, Port:int):
		return self.lib.SetHDMIPort(base_device_logical_address,Port)

	@register_mainloop_command("port")
	def ProcessSetHDMIPort(self, base_device_logical_address:str, Port:str):
		"change the HDMI port number of the CEC adapter."
		base_dev = str_to_logical_address(base_device_logical_address)
		if not self.lib.SetHDMIPort(base_dev,int(Port)):
			print("command failed",file=self.stdout)

	@multidispatch(str)
	def CommandTx(self,cmd:str):
		"""Send a command on the CEC line, string input"""
		return self.lib.Transmit(self.lib.CommandFromString(cmd))

	@multidispatch(int)
	def CommandTx(self,cmd:int):
		"""Send a command on the CEC line, integer input"""
		return self.lib.Transmit(cmd)

	# send a custom command
	@register_mainloop_command("tx","transmit")
	def ProcessCommandTx(self, data):
		"""Send a custom command"""
		cmd = self.lib.CommandFromString(data)
		print("transmit " + data,file=self.stdout)
		if self.lib.Transmit(cmd):
			print("command sent",file=self.stdout)
		else:
			print("failed to send command",file=self.stdout)

	# scan the bus and display devices that were found
	@register_mainloop_command("scan")
	def Scan(self):
		"""scan the bus and display devices that were found"""
		print("requesting CEC bus information ...",file=self.stdout)
		strLog = "CEC bus information\n===================\n"
		addresses = self.lib.GetActiveDevices()
#		activeSource = self.lib.GetActiveSource()
		x = 0
		while x < 15:
			if addresses.IsSet(x):
				vendorId = self.lib.GetDeviceVendorId(x)
				physicalAddress = self.lib.GetDevicePhysicalAddress(x)
				active = self.lib.IsActiveSource(x)
				cecVersion = self.lib.GetDeviceCecVersion(x)
				power = self.lib.GetDevicePowerStatus(x)
				osdName = self.lib.GetDeviceOSDName(x)
				strLog += (
					"device #"
					+ str(x)
					+ ": "
					+ self.lib.LogicalAddressToString(x)
					+ "\n"
				)
				strLog += "address:	   " + str(hex(physicalAddress)[2:]) + "\n"
				strLog += "active source: " + str(active) + "\n"
				strLog += "vendor:		" + self.lib.VendorIdToString(vendorId) + "\n"
				strLog += (
					"CEC version:   " + self.lib.CecVersionToString(cecVersion) + "\n"
				)
				strLog += "OSD name:	  " + osdName + "\n"
				strLog += (
					"power status:  " + self.lib.PowerStatusToString(power) + "\n\n\n"
				)
			x += 1
		print(strLog,file=self.stdout)

	@register_mainloop_command("volup")
	def VolumeUp(self):
		"""send a volume up command to the amp if present"""
		self.lib.VolumeUp()
	
	@register_mainloop_command("voldown")
	def VolumeDown(self):
		"""send a volume down command to the amp if present"""
		self.lib.VolumeDown()
	
	@register_mainloop_command("mute")
	def AudioToggleMute(self):
		"""send a mute/unmute command to the amp if present"""
		self.lib.AudioToggleMute()

	@register_mainloop_command("on")
	def PowerOnDevices(self, logical_address):
		"""power on the device with the given logical address"""
		logical_address = str_to_logical_address(logical_address)
		self.lib.PowerOnDevices(logical_address)

	
	def loop(self):
		if self.adapter:
			runLoop = True
			while runLoop:
				command = self.stdin.readline().strip().lower()
				if len(command)==0 or command.isspace():
					pass
				elif command == "q" or command == "quit":
					print("Exiting...",file=self.stdout)
					runLoop = False
				else:
					command = command.split()
					if command[0] in self.interactive_cmd:
						self.interactive_cmd[command[0]](self,*command[1:])
					else:
						print("unknown command.\n Type 'help' for a list of available commands",file=self.stdout)
		else:
			print("initialize the CEC client first!",file=self.stdout)


	# logging callback
	def LogCallback(self, level, time, message):
		if level & self.log_level == 0:
			return 0

		if level == cec.CEC_LOG_ERROR:
			levelstr = "ERROR:   "
		elif level == cec.CEC_LOG_WARNING:
			levelstr = "WARNING: "
		elif level == cec.CEC_LOG_NOTICE:
			levelstr = "NOTICE:  "
		elif level == cec.CEC_LOG_TRAFFIC:
			levelstr = "TRAFFIC: "
		elif level == cec.CEC_LOG_DEBUG:
			levelstr = "DEBUG:   "

		print(levelstr + "[" + str(time) + "]	 " + message,file = self.stdout)
		return 0

	# key press callback
	def KeyPressCallback(self, key, duration):
		print("[key pressed] " + str(key),file=self.stdout)
		return 0
	
	def switchback_badpa(self,cmd:str):
		"""
		This callback is very specific to this library author's setup.
		I have an hdmi switch between the soundbar and all my other devices, and that switch is dumb
		and confuse the hell out of everything that is connected through it.
		This callback watches for that confusion, and switch the signal route into an acceptable state (for my setup)
		"""
		print("[command received] " + cmd,file=self.stdout)
		# print("chopped command: ", cmd[4:])
		if cmd[4:] == "f:82:80:00":
			# print("switchback!",file=self.stdout)
			# self.bad_route = True
		# if cmd == ">> 5f:72:01":
			self.CommandTx("1f:82:11:00")
			# self.bad_route = False
		return 0


	# command received callback
	def CommandCallback(self, cmd:str):
		print("[command received] " + str(cmd),file=self.stdout)
		return 0

	def __init__(self):
		self.SetConfiguration()


# logging callback
def log_callback(level, time, message):
	return lib.LogCallback(level, time, message)


# key press callback
def key_press_callback(key, duration):
	return lib.KeyPressCallback(key, duration)


# command callback
def command_callback(cmd):
	return lib.CommandCallback(cmd)


def switchback_badpa(cmd):
	lib.switchback_badpa(cmd)

def default_cecclient():
	lib = pyCecClient()
	lib.SetLogCallback(lib.LogCallback)
	lib.SetKeyPressCallback(lib.KeyPressCallback )
	lib.SetCommandCallback(lib.CommandCallback)
	return lib
	
def callback_print(*args):
	print("callback printer: ",file=self.stdout)
	for a in args:
		print(a,' ',file=self.stdout)

if __name__ == "__main__":
	# initialise libCEC
	lib = default_cecclient()
	# lib.log_level = 0
	# lib.SetCommandCallback(lib.switchback_badpa)
	# initialise libCEC and enter the main loop
	lib.InitLibCec()
	# lib.SetHDMIPort(5,1)
	lib.loop()
	
