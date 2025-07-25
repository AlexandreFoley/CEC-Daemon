# CECdaemon
An attempt at daemonizing the cecclient.

Using libCEC python frontend, this project implements a cecclient in python, and using daemonocle and click, it daemonize said client.
The daemon can receive user input while running. Communication between the running daemon and the command line is done through named pipe, with a file lock for the daemon's input.

Launching and closing the client for every single command isn't an option if you want to have some registered callback monitoring the status and making adjustement to the the HDMI connection at all time, because only a single instance of libCEC can connect to the physical CEC device at any time.
Hence a daemon. 
And even if you don't need any callbacks doing background work, libcec has a lot of communication to do at launch and that takes some time (several seconds). Whatever it is you want to do will be done much quicker if the CECclient is already running and waiting for user input.

## dependencies	
ATTENTION: all the dependencies must be install in a way that make them available to the user that will own the daemon process.

-  libcec: A manual install might be necessary to have the python frontend. The AUR-git and Extra's packages does the trick on arch and its derivatives.
-  daemonocle: A python library that takes care of the forking, signal handling, cleanup and all other subtleties of creating a unix daemon.
-  click: A python library for the command line interface of the daemon.
-  filelock: A python library that supplies a syncronization device for interprocess communication.

## installation
(This instructions aren't nearly detailed enough as of now)
-  create a user for the daemon, make it member of the group that has access to the cecdevice (uucp with Archlinux and a USB connected device.) ($ useradd -M -s /usr/bin/nologin -G uucp cecdaemon)
-  create any call back you might need and modify the daemon's worker to register them. (for now only one callback function per type of callback possible...)
-  put a symlink to the bash script "cecdaemon" in the PATH.
-  In the daemon working directory, create a python virtual environment named env with access to global packages ($ python -m venv env --system-site-packages)
-  In the virtual environment, install locally the dependency of the project other than libcec ($ source ./env/bin/activate && pip install -I filelock daemonocle click && deactivate)
-  make adjustements to the service file (folders , paths, user and such)
-  make sure the cecdaemon user has access to the daemon's working directory.
-  copy the service file to systemd.
-  activate the service.

# Packaging in a more robust way
- compiling with nuitka seemed to have worked on the first try.
    - `python -m nuitka --standalone cecdaemon.py`
    - More testing is needed ofc. so far so good.
    - I suspect libcec has been pulled in to the "package". That's undesirable for proper distribution (forbidden by many distros), but I don't care enough. If there's ever interest in this project by other I can revisit this.
# TODO
- Make all the function that expect strings in pyCECclient robust to bad input. Must protect libCEC from it for better stability.
- improve the situation regarding files and working directory. currently "hardcoded" just after the import statements of cecdaemon.py
- Make the installation robust and easy. That is probably the hardest thing to do for that project and I might never do it.

## License
copyright 2021 Alexandre Foley (alexandre.foley@usherbrooke.ca)

The source files of this project are licensed under the GNU General Public License 
See LICENSE file in the project root for full license information.
