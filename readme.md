# CECdaemon
An attempt at daemonizing the cecclient.

Using libCEC python frontend, this library implements a cecclient in python, and using daemonocle and click, it daemonize said client.
The daemon can receive user input while running. Communication between the running daemon and the command line is done through named pipe, with a file lock for the daemon's input.

Launching and closing the client for every single command isn't an option if you want to have some registered callback monitoring the status and making adjustement to the the HDMI connection at all time, because only a single instance of libCEC can connect to the physical CEC device at any time.
Hence a daemon. 
And even if you don't need any callbacks doing background work, libcec has a lot of communication to do at launch and that takes some time (several seconds). Whatever it is you want to do will be done much quicker if the CECclient is already running and waiting for user input.

## dependencies	
ATTENTION: all the dependencies must be install in a way that make them available to the user that will own the daemon process.

-  libcec: A manual install might be necessary to have the python frontend. The AUR-git does the trick on arch and its derivatives.
-  daemonocle: A python library that takes care of the forking, signal handling, cleanup and all other subtleties of creating a unix daemon.
-  click: A python library for the command line interface of the daemon.
-  filelock: A python library that supplies a syncronization device for interprocess communication.

## installation
(This instructions aren't nearly detailed enough as of now)
-  create a user for the daemon, make it member of the group that has access to the cecdevice (uucp with Archlinux and a USB connected device.) ($ useradd -M -s /usr/bin/nologin -G uucp cecdaemon)
-  create any call back you might need and modify the daemon's worker to register them. (for now only one callback function per type of callback possible...)
-  put the cecdaemon in the PATH.
-  make adjustements to the service file (folders , paths, user and such)
-  make sure the cecdaemon user has access to the daemon's working directory.
-  copy the service file to systemd.
-  activate the service.

# TODO
- improve the situation regarding files and working directory. currently "hardcoded" just after the import statements of cecdaemon
