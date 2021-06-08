#! /usr/bin/env python3

# This file is part of the cecdaemon project
#
# copyright 2021 Alexandre Foley (alexandre.foley@usherbrooke.ca)
#
# Licensed under the GNU General Public License 
# See LICENSE file in the project root for full license information.

from typing import TextIO
import daemonocle as dae
import click
import cecclient
import time
import os
import sys
import threading
import filelock
import inspect


this_dir = "/home/salon/Documents/CEC-Daemon/"
daemonInput = this_dir + "daemoninput.fifo"
daemonOutput = this_dir + "daemonoutput.fifo"
daemonLock = daemonInput+".lock"
DONE = "éà\n"
ATTACHDONE="àéà\n"

"""
This must run with elevated permission to acquire the CEC ressource.
But I want users to be able to use the thing without elevated permission.
This means the access level for the fifo and the locks need to be set more carefully

since this is owned by uucp, those file, by default, require uucp level permission to write.
This default must be overwritten. 

"""

def generate_method_string(string_name:str,function_handle):
	"generate an exposed method that trigger an action from the cecdaemon, in a string to be read by exec"
	ArgSpec = inspect.getfullargspec(function_handle)
	if ArgSpec.varkw != None: #skip those for now... there ain't any, anyway
		return ''
	exec_string = "@dae.expose_action\n"
	args = ArgSpec.args[1:]
	call_string = ",".join(args)
	for arg in ArgSpec.args[1:]:
		exec_string+= "@click.argument('{}',nargs=1)\n".format(arg)
	if ArgSpec.varargs:
		exec_string+= "@click.argument(vararg,nargs=-1)\n"
		if call_string != '':
			call_string+=",*vararg"
		else:
			call_string = "*vararg"
		args.append("vararg")
	exec_string+= "def {}(self,{}):\n".format(string_name,','.join(args))
	exec_string+="\tself._forward_args('{}',{})\n\n".format(string_name,call_string)
	if function_handle.__doc__:
		exec_string += "{}.__doc__ = '''{}'''\n\n".format(string_name,function_handle.__doc__)
	return exec_string


def read_and_print_pipe(pipe_path:str,out:TextIO, stop = DONE, filter = DONE):
	"""open a pipe to read and print it all to stdout
	until the done sequence of character is received.
	Launch this function inside a thread to avoid locking on this function's I/O"""
	LS = len(stop)
	LF = len(filter)
	pipe = open(pipe_path,"r")
	for line in pipe:
		if line == '':#closed on the other side.
			out.write("The pipe was closed, the cec daemon was closed by another process, or crashed.\n")
			break
		if line[-LS:] == stop:
			out.write(line[:-LS]+'\n')
			break
		if line[-LF:] == filter:
			out.write(line[:-LF]+'\n')
		else:
			out.write(line)



def try_remove(filename:str):
	try:
		os.remove(filename)
	except:
		pass


class cecdaemon(dae.Daemon):

	def _deamon_main(self):
		"""
		daemon for controlling the CEC device
		"""
		# try:
		# 	##this will need to change to reflect the the need to belong to uucp on arch
		# 	#This is almost certainly asking for too much.
		# 	os.mkdir('/etc/tmp_CECpermtest')
		# 	os.rmdir('/etc/tmp_CECpermtest')
		# except PermissionError as e:
		# 	if (e.errno == 13):
		# 	   sys.exit("Elevated permission are necessary to acquire the cec device")
		try_remove(daemonOutput)#make sure it's clean
		try_remove(daemonInput)#make sure it's clean
		os.mkfifo(daemonInput,mode=0o666) #for some reason the mode is getting ignored here.
		os.chmod(daemonInput,0o666)
		os.mkfifo(daemonOutput,mode=0o644)#read only for everyone but the owner.
		lock = filelock.FileLock(daemonInput+'.lock', timeout=1)
		self.cec = cecclient.pyCecClient(deviceType=cecclient.CEC_DEVICE_TYPE_PLAYBACK_DEVICE)
		self.cec.SetLogCallback(self.cec.LogCallback)
		self.cec.SetKeyPressCallback(self.cec.KeyPressCallback )
		self.cec.SetCommandCallback(self.cec.switchback_badpa)#switchback badpath probably shouldn't be built in.
		#it need to be able to acess the cec controller without having it in it's arguments none-the-less.
		#if it's not baked in the CECclient, it's baked in the daemon.
		self.cec.InitLibCec()
		self.cec.SetHDMIPort(5,1)
		# time.sleep(0.5)
		if self.cec.GetActiveSource() ==-1:
			self.cec.CommandActiveSource()
		print("opening daemonInput")
		self.input = open(daemonInput,"r")
		print("opening daemonoutput")
		self.output = open(daemonOutput,"w",buffering=1)
		self._repl(self.input,self.output)
	
	def _forward_args(self,*args):
		"""forward all its arguments into the daemoninput named pipe.
		Acquires a file lock before it tries to do so."""
		pid = self._read_pid_file()
		if pid:
			handle = threading.Thread(target = read_and_print_pipe,args = (daemonOutput,sys.stdout))
			handle.start()
			lock = filelock.FileLock(daemonInput+'.lock', timeout=1)
			with lock.acquire():
				pipe = open(daemonInput,"w")
				for a in args:
					pipe.write(a+' ')
				pipe.write(DONE)
				pipe.flush()#DAMN!
			handle.join()
		else:
			self._echo_warning('{name} is not running'.format(name=self.name))

	@dae.expose_action
	def attach(self):
		'''
		attach the console to the cec client output.
		all output from the cecclient (like log info from callbacks) is printed for the duration
		'''
		output_pipe = open(daemonOutput,"r")
		handle = threading.Thread(target = read_and_print_pipe,args = (output_pipe,sys.stdout,ATTACHDONE))
		handle.start()
		self._forward_args("attach")
		input()
		self._forward_args("detach")
		handle.join()

	#for each of the interactive commands of pyCeCclient, generate a command line command for the daemon
	for string_name in cecclient.pyCecClient.interactive_cmd:
		exec_string = generate_method_string(string_name,cecclient.pyCecClient.interactive_cmd[string_name])
		exec(exec_string)

	def _repl(self,input:TextIO,output:TextIO):
		"""the read eval print loop of the daemon.
		 Waits for user input received by calling the exposed function of the daemon"""
		runLoop = True
		print("reached repl!")
		while runLoop:
			print("looped!")
			command = [] 
			while runLoop:
				line = input.readline()
				if line[-3:] == DONE:
					command.extend(line[:-3].strip().lower().split())#The writer is leaving.
					break
				if line == '': #writers gone.
					command = [] 
					input.close()
					input = open(daemonInput,'r') #locks until there's a writer
					continue
				line = line.strip().lower()
				if line != '': 
					command.extend(line.split())
			if len(command)==0:
				pass
			else:
				if command[0] == "attach":
					output.write("press enter to detach.")
					time.sleep(1)
					self.attach_guard, self.cec.stdout = self.cec.stdout, output
				elif command[0] == "detach":
					self.cec.stdout =self.attach_guard
					output.write(ATTACHDONE)
					output.flush()
				elif command[0] in self.cec.interactive_cmd:
					out_guard = self.cec.stdout
					self.cec.stdout = output # switch the output sink just for this command execution time
					self.cec.interactive_cmd[command[0]](self.cec,*command[1:])
					self.cec.stdout = out_guard
				else:
					print("Unknown command.\n Use'--help' argument for a list of available commands",file=output)
				output.write(DONE)
				output.flush()
	
	def _builtin_shutdown(self,message,code):
		try_remove(daemonInput)
		try_remove(daemonOutput)
		try_remove(daemonLock)

	def _shutdown(self, message=None, code=0):
		"""Shutdown and cleanup everything."""
		if self._shutdown_complete:
			# Make sure we don't accidentally re-run the all cleanup
			exit(code)
		#cleanup associated with self.main
		self._builtin_shutdown(message,code)
		# Call the shutdown hook with a message suitable for
		# logging and the exit code
		self._run_hook('shutdown', message, code)

		if self.pid_file is not None:
			self._close_pid_file()

		self._shutdown_complete = True
		exit(code)
	

	def __init__(
        self,
        # Basic stuff
        name=None,
        worker=None,
        detach=True,
        # Paths
        pid_file=None,
        work_dir='/',
        stdout_file=None,
        stderr_file=None,
        chroot_dir=None,
        # Environmental stuff that most people probably won't use
        uid=None,
        gid=None,
        umask=0o22,
        close_open_files=False,
        # Related to specific actions
        hooks=None,
        stop_timeout=10,
        # Deprecated arguments
        prog=None,
        pidfile=None,
        workdir='/',
        chrootdir=None,
        shutdown_callback=None,):
		meta_worker = 0
		if worker:
			def imeta_worker():
				handle = threading.Thread(target = worker,args = (),daemon=True)
				assert(handle.isDaemon())
				handle.start()
				self._deamon_main()
			meta_worker = imeta_worker
		else:
			meta_worker = self._deamon_main
		super().__init__(name=name, worker=meta_worker, detach=detach, pid_file=pid_file, work_dir=work_dir, stdout_file=stdout_file, stderr_file=stderr_file, chroot_dir=chroot_dir, uid=uid, gid=gid, umask=umask, close_open_files=close_open_files, hooks=hooks, stop_timeout=stop_timeout, prog=prog, pidfile=pidfile, workdir=workdir, chrootdir=chrootdir, shutdown_callback=shutdown_callback)


if __name__ == '__main__':
	daemon = cecdaemon(
		pid_file=this_dir+'/cecdaemon.pid',
		# detach = False,
	)
	daemon.cli()