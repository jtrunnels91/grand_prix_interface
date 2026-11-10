# Note: The derbynet url will be the following:
#
# http://<host_ip>/derbynet/
#
# Where host_ip may be retrieved by running "hostname -I" on the hosting laptop


import serial
import time
import requests
import xmltodict
import json
import datetime
import numpy as np

from multiprocessing.pool import ThreadPool


class YachtTimerMonitor:
    def __init__(
            self,
            derby_net_url="http://192.168.68.104/derbynet/",
            heartbeat_period=1,
            enable_remote_start=True,
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

        self.thread_pool.apply_async(self.post_messages_loop)


    def get_race_results(self):
        time_list = [1,2,3,4]

        return time_list

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

                time_list= self.get_race_results()

                if time_list is not None:
                    print(time_list)
                    self.post_finished(time_list)


    def get_session_cookie(self):
        self.session_cookie = None
        req = self.post_generic_message("action=role.login&name=Timer&password=")
        my_response_dict = self.req_response_to_dict(req)
        if my_response_dict['outcome']['code']=='success':

            self.session_cookie = req.headers['Set-Cookie'].split(';')[0]

    def post_heartbeat(self):
        hb_req = self.post_generic_message("action=timer-message&message=HEARTBEAT")
        self.parse_response(hb_req)
        print(hb_req.text)

        return hb_req

    def post_hello(self):
        # Hello
        hello_req = self.post_generic_message("action=timer-message&message=HELLO")
        self.parse_response(hello_req)

    def post_id(self):
        #Identified
        id_req = self.post_generic_message("action=timer-message&message=IDENTIFIED")
        self.parse_response(id_req)

    def post_finished(self, time_list):
        time_list = [ t if t > 0 else 30.0 for t in time_list]
        print(time_list)
        place_list = [None for i in time_list]
        current_place = 1
        while None in place_list:
            modified_time_list = [
                time_list[i] if place_list[i] is None
                else 100.0
                for i in range(len(time_list))
            ]
            next_place_lane = np.argmin(modified_time_list)
            place_list[next_place_lane] = current_place
            current_place += 1

        time_message = (
            "action=timer-message"
            + "&message=FINISHED"
            + "&roundid=" + str(self.roundid)
            + "&heat=" + str(self.heat)
        )
        lane_counter = 1
        for finish_time, finish_place in zip(time_list, place_list):
            time_message += ("&lane" + str(lane_counter) + "=" + str(finish_time))
            time_message += ("&place" + str(lane_counter) + "=" + str(finish_place))
            lane_counter += 1

        # Finished
        print(time_message)
        response = self.post_generic_message(time_message)
        self.parse_response(response)

    def parse_response(self, response):
        response = self.req_response_to_dict(response)

        if 'action-response' in response:
            response = response['action-response']
        if 'heat-ready' in response:
            self.round = response['heat-ready']['@round']
            self.roundid = response['heat-ready']['@roundid']
            self.heat = response['heat-ready']['@heat']

        print(response)
        print(self.round)
        print(self.roundid)
        print(self.heat)

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


my_mon = YachtTimerMonitor()
my_mon.establish_session()