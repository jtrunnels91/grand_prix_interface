# Note: The derbynet url will be the following:
#
# http://<host_ip>/derbynet/
#
# Where host_ip may be retrieved by running "hostname -I" on the hosting laptop



import time
import requests
import xmltodict
import json
import datetime
import numpy as np

from multiprocessing.pool import ThreadPool


class DerbyNetInterface:
    def __init__(
            self,
            derby_net_url="http://192.168.68.117/derbynet/",
            heartbeat_period=0.1,
            enable_remote_start=True,
            timer_interface=None
    ):
        self.enable_remote_start = enable_remote_start
        self.session_cookie = None
        self.thread_pool = ThreadPool(4)

        self.derby_net_url = derby_net_url
        self.heartbeat_period = heartbeat_period

        self.last_heartbeat_time = datetime.datetime.now()
        self.continue_post_messages = True

        self.round = -100
        self.roundid = -100
        self.heat = -100
        self.heat_ready_to_set = False
        self.remote_start = False
        self.lanes_enabled = None

        self.timer_interface = timer_interface

    def req_response_to_dict(self, response):
        if response.headers['Content-Type'] == 'application/json; charset=utf-8':
            result = json.loads(response.content.decode())
        elif  response.headers['Content-Type'] == 'text/xml; charset=utf-8':
            result = xmltodict.parse(response.content.decode())
        else:
            raise ValueError("Unknown Content-Type: '" + str(response.headers['Content-Type']))
        return result

    def establish_session(
            self,
    ):
        self.get_session_cookie()

        while self.session_cookie is None:
            self.get_session_cookie()

        self.post_hello()
        self.post_id()
        self.start_communications_loop()

    def start_communications_loop(self):
        def handle_error(error):
            print("||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")
            print("WHILE INTERACTING WITH DERBYNET, TIMER ENCOUNTERED AN ERROR:")
            print("Communications loop has stopped.")
            print("To restart, call <DerbyNetInterface>.start_communications_loop")
            raise(error)

        self.thread_pool.apply_async(self.post_messages_loop, error_callback=handle_error)


    def get_race_results(self):

        finish_times = None
        finish_places = None
        if self.timer_interface is None:
            finish_times = {
                1: 1, 2: 2, 3: 3, 4: 4,
            }
            finish_places = {
                1: 1, 2: 2, 3: 3, 4: 4,
            }

        else:
            finish_times, finish_places = self.timer_interface.get_race_results()

        return finish_times, finish_places

    def set_next_heat(self):
        try:
            heat_ready_success = self.timer_interface.set_next_race(
                self.lanes_enabled[1],
                self.lanes_enabled[2],
                self.lanes_enabled[3],
                self.lanes_enabled[4],
            )
        except Exception as e:
            exception_string = str(e)
        if heat_ready_success:
            print("Successfully set next race")
        else:
            print("Setting next race failed with following error: \r\n" + exception_string)
        self.heat_ready_to_set = False

    def start_race(self):
        print("Attempting to start next race")
        start_success = False
        exception_string = ""


        try:
            start_success = self.timer_interface.start_race()
        except Exception as e:
            exception_string = str(e)

        if start_success:
            print("Successfully started race")
            self.remote_start = False
        else:
            print("Race failed to start with following error: \r\n" + exception_string)
            self.remote_start = False


    def post_messages_loop(self):
        while self.continue_post_messages:
            self.post_messages()

    def post_messages(self):
        current_time = datetime.datetime.now()
        if (
                (current_time - self.last_heartbeat_time).total_seconds()
                > self.heartbeat_period
        ):
            if self.session_cookie is not None:
                self.post_heartbeat()

                self.last_heartbeat_time = current_time

                if self.heat_ready_to_set:
                    self.set_next_heat()

                if self.remote_start:
                    self.start_race()
                    self.post_started()

                finish_times, finish_places= self.get_race_results()

                if finish_times is not None or finish_places is not None:
                    print("Received finish times and places:")
                    print(finish_times)
                    print(finish_places)
                    self.post_finished(finish_times, finish_places)


    def get_session_cookie(self):
        self.session_cookie = None
        req = self.post_generic_message("action=role.login&name=Timer&password=")
        my_response_dict = self.req_response_to_dict(req)
        if my_response_dict['outcome']['code']=='success':

            self.session_cookie = req.headers['Set-Cookie'].split(';')[0]

    def post_heartbeat(self):
        hb_req = self.post_generic_message("action=timer-message&message=HEARTBEAT")
        self.parse_response(hb_req)
        return hb_req

    def post_hello(self):
        # Hello
        hello_req = self.post_generic_message("action=timer-message&message=HELLO")
        self.parse_response(hello_req)

    def post_id(self):
        #Identified
        id_req = self.post_generic_message("action=timer-message&message=IDENTIFIED")
        self.parse_response(id_req)

    def post_started(self):
        time_message = (
            "action=timer-message"
            + "&message=STARTED"
        )
        response = self.post_generic_message(time_message)
        self.parse_response(response)

    def post_finished(self, finish_times=None, finish_places=None):

        time_message = (
            "action=timer-message"
            + "&message=FINISHED"
            + "&roundid=" + str(self.roundid)
            + "&heat=" + str(self.heat)
        )
        if finish_times is not None:
            for finish_lane, finish_time in finish_times.items():
                if finish_time:
                    time_message += (
                        "&lane" + str(finish_lane)
                        + "=" + str(finish_time.total_seconds())
                    )

        if finish_places is not None:
            for finish_lane, finish_place in finish_places.items():
                if finish_place > 0:
                    time_message += ("&place" + str(finish_lane) + "=" + str(finish_place))


        # Finished
        response = self.post_generic_message(time_message)
        self.parse_response(response)

    def parse_response(self, response):
        response = self.req_response_to_dict(response)

        if 'action-response' in response:
            response = response['action-response']
        if 'heat-ready' in response:
            self.heat_ready_to_set = True
            self.round = response['heat-ready']['@round']
            self.roundid = response['heat-ready']['@roundid']
            self.heat = response['heat-ready']['@heat']
            lane_mask = int(response['heat-ready']['@lane-mask'])
            lane1_mask = 0b0001
            lane2_mask = 0b0010
            lane3_mask = 0b0100
            lane4_mask = 0b1000
            self.lanes_enabled = {
                1: (lane_mask & lane1_mask)>0,
                2: (lane_mask & lane2_mask)>0,
                3: (lane_mask & lane3_mask)>0,
                4: (lane_mask & lane4_mask)>0,
            }

        if 'remote-start' in response:
            self.remote_start = True

        if 'abort' in response:
            self.timer_interface.abort_race()

        # print(response)
        # print("Heat ready: " + str(self.heat_ready))
        # print("Round: " + str(self.round))
        # print("Round ID: " + str(self.roundid))
        # print("Heat: " + str(self.heat))
        # print("Lanes enabled: " + str(self.lanes_enabled))
        # print("Remote start: " + str(self.remote_start))
    def post_generic_message(self, message_text):
        if self.enable_remote_start:
            message_text = "remote-start=YES&" + message_text
        content_length = len(message_text)
        header_dict = {
            'Host': 'localhost',
            "Accept": 'text/html, image/gif, image/jpeg, *; q=.2, */*; q=.2',
            "Connection": 'keep-alive',
            "Content-type": "application/x-www-form-urlencoded",
            "Content-Length": str(content_length),
        }
        if self.session_cookie is not None:
            header_dict["Cookie"] = self.session_cookie

        req = requests.post(
            self.derby_net_url + "action.php",
            headers=header_dict,
            data=message_text
        )
        return req

# Heartbeat

if __name__ == 'main':
    my_mon = YachtTimerMonitor()
    my_mon.establish_session()