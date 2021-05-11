#! /usr/bin/env python

import daemonocle as dae
import cec
import time
import os
import sys
import errno

def deamon_main():
    try:
        os.mkdir('/etc/tmp_CECpermtest')
        os.rmdir('/etc/tmp_CECpermtest')
    except PermissionError as e:
        if (e.errno == 13):
           sys.exit("Elevated permission are necessary to acquire the cec device")
    cec.init()
    #register baked in callbacks here.
    while(True):# i will replace this with something else eventually..
        time.sleep(10)

class cecdaemon(dae.Daemon):
    @dae.expose_action
    def mute(self):
        """mute sound"""
        cec.mute()
        time.sleep(0.5)

    @dae.expose_action
    def volume_down(self):
        """Reduce volume by one."""
        cec.volume_down()
        time.sleep(0.5)

    @dae.expose_action
    def volume_up(self):
        """Increase volume by one."""
        cec.volume_up()
        time.sleep(0.5)

cec.transmit()
cec.
if __name__ == '__main__':
    daemon = cecdaemon(
        worker=deamon_main,
        pid_file='/var/run/cecdaemon.pid',
    )
    daemon.do_action(sys.argv[1])
