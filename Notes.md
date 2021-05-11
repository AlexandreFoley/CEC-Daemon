## volume changes

when pressing the volume up button on the TV remote cec-client observes
```
    TRAFFIC: [          287879]     >> 05:44:41
    COMMENT: TV to Audio, volume up pressed
    TRAFFIC: [          287903]     >> 05:71
    COMMENT: TV to Audio, give audio status
    TRAFFIC: [          288051]     >> 50:7a:06
    COMMENT: Audio to TV, status report: volume is 6, mute is off
    DEBUG:   [          288051]     >> Audio (5): audio status changed from  5 to  6
    TRAFFIC: [          288271]     >> 05:45
    COMMENT: TV to Audio, button released
    TRAFFIC: [          288340]     >> 05:71
    COMMENT: TV to Audio, give audio status
    TRAFFIC: [          288390]     >> 50:7a:08
    COMMENT: Audio to TV, status report: volume is 8, mute is off
    DEBUG:   [          288390]     >> Audio (5): audio status changed from  6 to  8
    TRAFFIC: [          288673]     >> 50:7a:08
    COMMENT: Audio to TV, status report: volume is 8, mute is off
```
a volume down press gives:
```
TRAFFIC: [          378313]     >> 05:44:42
TRAFFIC: [          378337]     >> 05:71
TRAFFIC: [          378484]     >> 50:7a:07
DEBUG:   [          378484]     >> Audio (5): audio status changed from  8 to  7
TRAFFIC: [          378705]     >> 05:45
TRAFFIC: [          378775]     >> 05:71
TRAFFIC: [          378825]     >> 50:7a:05
DEBUG:   [          378825]     >> Audio (5): audio status changed from  7 to  5
TRAFFIC: [          379114]     >> 50:7a:05
```
when pressing volume up on the soundbar remote:
```
TRAFFIC: [          653714]     >> 50:7a:08
DEBUG:   [          653714]     >> Audio (5): audio status changed from  5 to  8
```

volume down:
```
TRAFFIC: [          704814]     >> 50:7a:05
DEBUG:   [          704814]     >> Audio (5): audio status changed from  8 to  5
```

It seems it's only a status report when we use the soudbar remote.

With the TV remote an interesting exchange happens.
The key to controling the volume is there.

## automatic screen shutdown

KDE doesn't have any events for the activation of the screen energy saver, only for lockscreen on and off...
But it does offer to run a script after some time spent idling.
Using the python module pynput, I could create a script that upon launch, shutdown the screen and then monitor the keyboard and mouse for any actions. As soon as any action is detected, it turns the screen back on, and shut itself down.

## hdmi signal path monitoring
For the signal to get from the computer to the screen, a particular path is needed: the soundbar stand in between the tv and everything else. ARC is not available on the TV. For some reason the soundbar tends to switch to ARC mode when the TV turn on or a device request a signal path change. For the soundbar, ARC is never right. Passthrough is the only mode in which something shows on the TV screen.

For that reason, we need a deamon to run that monitor the status of the soundbar on the CECline, and whenever the soundbar switches to ARC, put it in passthough, as we can assume something wants to display on screen when ARC mode is tripped.

The Deamonocle python library offer us a way to create such a deamon that can also take on the other responsability we will have to give to it (automatic screen shutdown at the very least). It is necessary that the deamon be able to do more than just the monitoring, because only one application can aquire a lock on the CEC device at any time.

The other task of the daemon will be accomplished by calling the daemon with options and perhaps arguments to launch other tasks.

A service must then be created to run the daemon on computer launch.
