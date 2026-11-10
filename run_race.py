# Note: The derbynet url will be the following:
#
# http://<host_ip>/derbynet/
#
# Where host_ip may be retrieved by running "hostname -I" on the hosting laptop
#
# Also note: You must run "sud pigpiod" to interface with the servos

import race_timer_monitor as rtm
ti = rtm.timer_interface.RaceManager(
    test_mode=False,
    max_race_time=60.0
)
if True:
    dni = rtm.derbynet.DerbyNetInterface(
        timer_interface=ti,
        derby_net_url="http://192.168.1.238/derbynet/",
    )
    dni.establish_session()