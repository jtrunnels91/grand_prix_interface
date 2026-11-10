
import serial
import time
import requests
import xmltodict
import json
import datetime
import numpy as np

from multiprocessing.pool import ThreadPool


class TimerMonitor:
    def __init__(
            self,
            port='/dev/ttyUSB0',
            baudrate=9600,
            timeout=1,
            inter_byte_timeout=0.01,
            derby_net_url="http://192.168.2.45/derbynet/",
            heartbeat_period=1,
    ):
        self.serial_port = None
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.inter_byte_timeout = inter_byte_timeout
        self.session_cookie = None

        self.thread_pool = ThreadPool(4)

        self.derby_net_url = derby_net_url
        self.heartbeat_period = heartbeat_period

        self.last_heartbeat_time = datetime.datetime.now()
        self.continue_post_messages = True

        self.roundid = -100
        self.heat = -100

    def open_serial_port(self):
        self.serial_port = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            inter_byte_timeout=self.inter_byte_timeout
        )
        while not self.serial_port.is_open:
            pass
        self.serial_port.flush()

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
        serial_result = None
        if self.serial_port is not None and self.serial_port.is_open:
            serial_result = self.serial_port.read_all()
        time_list = None

        if serial_result is not None:
            serial_result = serial_result.decode()
            split_result = serial_result.split('\r')
            if len(split_result) > 4:
                time_list = [
                    (float(sub_res.split(':')[0]) * 60)
                    + float(sub_res.split(':')[1])
                    for sub_res in split_result[0:4]
                ]
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
        req = requests.post(
            self.derby_net_url + "action.php",
            headers={
                'Host': 'localhost',
                "Accept": 'text/html, image/gif, image/jpeg, *; q=.2, */*; q=.2',
                "Connection": 'keep-alive',
                "Content-type": "application/x-www-form-urlencoded",
                "Content-Length": '33',
            },
            data="action=role.login&name=Timer&password="
        )
        my_response_dict = self.req_response_to_dict(req)
        if my_response_dict['outcome']['code']=='success':

            self.session_cookie = req.headers['Set-Cookie'].split(';')[0]

    def post_heartbeat(self):
        hb_req = requests.post(
            self.derby_net_url + "action.php",
            headers={
                'Host': 'localhost',
                "Accept": 'text/html, image/gif, image/jpeg, *; q=.2, */*; q=.2',
                "Connection": 'keep-alive',
                "Content-type": "application/x-www-form-urlencoded",
                "Content-Length": '38',
                "Cookie": self.session_cookie
            },
            data="action=timer-message&message=HEARTBEAT"
        )
        self.parse_response(hb_req)

        return hb_req

    def post_hello(self):
        # Hello
        hello_req = requests.post(
            self.derby_net_url + "action.php",
            headers={
                'Host': 'localhost',
                "Accept": 'text/html, image/gif, image/jpeg, *; q=.2, */*; q=.2',
                "Connection": 'keep-alive',
                "Content-type": "application/x-www-form-urlencoded",
                "Content-Length": '34',
                "Cookie": self.session_cookie
            },
            data="action=timer-message&message=HELLO"
        )
        self.parse_response(hello_req)

    def post_id(self):

        #Identified
        id_req = requests.post(
            self.derby_net_url + "action.php",
            headers={
                'Host': 'localhost',
                "Accept": 'text/html, image/gif, image/jpeg, *; q=.2, */*; q=.2',
                "Connection": 'keep-alive',
                "Content-type": "application/x-www-form-urlencoded",
                "Content-Length": '39',
                "Cookie": self.session_cookie
            },
            data="action=timer-message&message=IDENTIFIED"
        )
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

        message_len = str(len(time_message))
        # Finished
        print(time_message)
        response = requests.post(
            self.derby_net_url + "action.php",
            headers={
                'Host': 'localhost',
                "Accept": 'text/html, image/gif, image/jpeg, *; q=.2, */*; q=.2',
                "Connection": 'keep-alive',
                "Content-type": "application/x-www-form-urlencoded",
                "Content-Length": message_len,
                "Cookie": self.session_cookie
            },
            data=time_message
        )
        self.parse_response(response)

    def parse_response(self, response):
        response = self.req_response_to_dict(response)

        if 'action-response' in response:
            response = response['action-response']
        if 'heat-ready' in response:
            self.round = response['heat-ready']['@round']
            self.roundid = response['heat-ready']['@roundid']
            self.heat = response['heat-ready']['@heat']
# Heartbeat


my_mon = TimerMonitor()
my_mon.open_serial_port()
my_mon.establish_session()
# while True:
#     pass