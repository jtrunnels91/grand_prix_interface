import RPi.GPIO as GPIO
import pigpio
import datetime as dt
import time
import random
import numpy as np


class RaceManager:
    IN_PROGRESS = "IN PROGRESS"
    FINISHED = "FINISHED"
    READY = "READY"
    IDLE = "IDLE"
    RED = 1
    BLUE = 2
    GREEN = 3
    YELLOW = 4
    def __init__(
            self,
            LEFT_SERVO_PIN = 13,
            RIGHT_SERVO_PIN=12,
            RED_PIN = 26,
            BLUE_PIN = 19,
            GREEN_PIN = 6,
            YELLOW_PIN = 5,
            SERVO_CLOSE = 2.5,
            SERVO_OPEN = 7.5,
            red_enabled=True,
            blue_enabled=True,
            green_enabled=True,
            yellow_enabled=True,
            test_mode=False,
            max_race_time=15.0,
            max_test_race_time=20.0,
            left_servo_closed = 600,
            left_servo_open = 1600,
            right_servo_closed= 2400,
            right_servo_open= 1400

    ):
        self.max_race_time = max_race_time
        self.max_test_race_time = max_test_race_time

        self.LEFT_SERVO_PIN = LEFT_SERVO_PIN
        self.RIGHT_SERVO_PIN = RIGHT_SERVO_PIN
        self.RED_PIN = RED_PIN
        self.BLUE_PIN = BLUE_PIN
        self.GREEN_PIN = GREEN_PIN
        self.YELLOW_PIN = YELLOW_PIN

        self.SERVO_CLOSE = SERVO_CLOSE
        self.SERVO_OPEN = SERVO_OPEN

        self.gpio_configured = False

        self.race_status = self.IDLE
        self.race_start_time = None
        self.race_finish_place = 0

        self.LEFT_SERVO_CLOSED = left_servo_closed
        self.LEFT_SERVO_OPEN = left_servo_open

        self.RIGHT_SERVO_CLOSED = right_servo_closed
        self.RIGHT_SERVO_OPEN = right_servo_open

        self.lane_finish_times = {
            self.RED: None,
            self.BLUE: None,
            self.GREEN: None,
            self.YELLOW: None
        }
        self.lane_finish_places = {
            self.RED: None,
            self.BLUE: None,
            self.GREEN: None,
            self.YELLOW: None
        }
        self.lanes_enabled = {
            self.RED: red_enabled,
            self.BLUE: blue_enabled,
            self.GREEN: green_enabled,
            self.YELLOW: yellow_enabled
        }

        self.test_mode = test_mode
        self.test_mode_finish_time = None
        self.configure_gpio()


    def set_next_race(
        self,
        red_enabled=True,
        blue_enabled=True,
        green_enabled=True,
        yellow_enabled=True
    ):
        if self.race_status == self.IDLE or self.race_status == self.READY:
            self.lanes_enabled = {
                self.RED: red_enabled,
                self.BLUE: blue_enabled,
                self.GREEN: green_enabled,
                self.YELLOW: yellow_enabled
            }
            self.race_status = self.READY
            self.close_gates()
        else:
            raise ValueError(
                "Not yet ready to start new heat.  Current race status is " + str(self.race_status)
            )

        return True

    def abort_race(self):
        self.race_status = self.IDLE
        print("Aborting race")


    def end_race(self):
        for lane in self.lane_finish_places:
            if self.lane_finish_places[lane] is None:
                self.lane_finish_places[lane] = -1
        self.race_status = self.FINISHED
        self.print_results()

    def test_race_end(self):
        if (
                self.test_mode
                and self.race_status == self.IN_PROGRESS
                and self.test_mode_finish_time < dt.datetime.now()
        ):
            self.end_race()

    def mercy_kill(self):
        if self.race_status == self.IN_PROGRESS:
            t_current = dt.datetime.now()
            total_race_seconds = (t_current - self.race_start_time).total_seconds()
            if (
                    self.max_race_time is not None
                    and total_race_seconds > self.max_race_time
            ):
                print("Ending race: Mercy kill")
                for lane in self.lane_finish_times:
                    if self.lane_finish_times[lane] is None:
                        self.lane_finish_times[lane] = (dt.datetime.now() - self.race_start_time)
                        self.lane_finish_places[lane] = self.race_finish_place + 1
                        self.race_finish_place += 1

                if all([d is not None for d in self.lane_finish_times.values()]):

                    self.end_race()

    def get_race_results(self):
        self.test_race_end()
        self.mercy_kill()
        finish_times = None
        finish_places = None
        if self.race_status == self.FINISHED:
            finish_times = {**self.lane_finish_times}
            finish_places = {**self.lane_finish_places}
            self.race_status = self.IDLE
        return finish_times, finish_places

    def start_race(self):
        if self.race_status != self.READY:
            raise ValueError(
                "Not yet ready to start race.  Current race status is " + str(self.race_status)
            )
        if not self.gpio_configured:
            raise ValueError(
                "Must configure GPIO first"
            )
        self.lane_finish_times = {
            lane: (None if enabled else False) for lane, enabled in self.lanes_enabled.items()
        }
        self.lane_finish_places = {
            lane: None for lane in self.lanes_enabled.keys()
        }

        lanes_blocked = self.check_lanes_blocked()
        if lanes_blocked is not None:
            raise ValueError(lanes_blocked)

        self.open_gates()
        self.race_start_time = dt.datetime.now()
        self.race_status = self.IN_PROGRESS
        self.race_finish_place = 0

        if self.test_mode is True:
            lane_finish_times = {
                lane: (
                    dt.timedelta(seconds=random.uniform(2,self.max_test_race_time))
                    if enabled else False
                )
                for lane, enabled in self.lanes_enabled.items()
            }

            time_list = [t.total_seconds() if t else False for t in lane_finish_times.values()]
            max_time = np.max([t for t in time_list if t])

            self.test_mode_finish_time = self.race_start_time + dt.timedelta(seconds=max_time)
            self.lane_finish_times = lane_finish_times
            place_list = [None if t else -1 for t in time_list]
            current_place = 1

            while None in place_list:
                modified_time_list = [
                    time_list[i] if place_list[i] is None
                    else 1000.0
                    for i in range(len(time_list))
                ]
                next_place_lane = np.argmin(modified_time_list)
                place_list[next_place_lane] = current_place
                current_place += 1
                self.lane_finish_places = {
                    lane: place
                    for lane, place in zip(self.lane_finish_times.keys(), place_list)
                }

        return True

    def close_gates(self):
        self.pwm.set_servo_pulsewidth(self.LEFT_SERVO_PIN, self.LEFT_SERVO_CLOSED)
        self.pwm.set_servo_pulsewidth(self.RIGHT_SERVO_PIN, self.RIGHT_SERVO_CLOSED)

    def open_gates(self):
        self.pwm.set_servo_pulsewidth(self.LEFT_SERVO_PIN, self.LEFT_SERVO_OPEN)
        self.pwm.set_servo_pulsewidth(self.RIGHT_SERVO_PIN, self.RIGHT_SERVO_OPEN)

    def print_results(self):
        print("RACE RESULTS:")
        for key, value in self.lane_finish_times.items():
            if value:
                print(str(key) + ": " + str(value.total_seconds()))
        for key, value in self.lane_finish_places.items():
            if value:
                print(str(key) + ": " + str(value))

    def break_beam_callback(self, channel):
        if self.race_status == self.IN_PROGRESS and not GPIO.input(channel):
            if channel == self.RED_PIN:
                lane = self.RED
            elif channel == self.BLUE_PIN:
                lane = self.BLUE
            elif channel == self.GREEN_PIN:
                lane = self.GREEN
            elif channel == self.YELLOW_PIN:
                lane = self.YELLOW
            if self.lane_finish_times[lane] is None:
                t_current = dt.datetime.now()
                self.lane_finish_times[lane] = (
                    t_current - self.race_start_time
                )
                self.lane_finish_places[lane] = self.race_finish_place + 1
                self.race_finish_place += 1

            if all([d is not None for d in self.lane_finish_times.values()]):

                self.end_race()


    def __del__(self):
        print("Cleaning up GPIO")
        GPIO.cleanup()

    def configure_gpio(self):
        GPIO.setmode(GPIO.BCM)

        if self.lanes_enabled[self.RED]:
            GPIO.setup(self.RED_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                self.RED_PIN,
                GPIO.FALLING,
                callback=self.break_beam_callback
            )

        if self.lanes_enabled[self.BLUE]:
            GPIO.setup(self.BLUE_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                self.BLUE_PIN,
                GPIO.FALLING,
                callback=self.break_beam_callback
            )
        if self.lanes_enabled[self.GREEN]:
            GPIO.setup(self.GREEN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                self.GREEN_PIN,
                GPIO.FALLING,
                callback=self.break_beam_callback
            )
        if self.lanes_enabled[self.YELLOW]:
            GPIO.setup(self.YELLOW_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                self.YELLOW_PIN,
                GPIO.FALLING,
                callback=self.break_beam_callback
            )

        self.pwm = pigpio.pi()
        self.pwm.set_mode(self.LEFT_SERVO_PIN, pigpio.OUTPUT)
        self.pwm.set_mode(self.RIGHT_SERVO_PIN, pigpio.OUTPUT)

        self.gpio_configured = True


    def check_lanes_blocked(self):
        red_blocked = False
        blue_blocked = False
        green_blocked = False
        yellow_blocked = False
        # Check that all four lanes are clear
        if self.lanes_enabled[self.RED] and not GPIO.input(self.RED_PIN):
            red_blocked = True
        if self.lanes_enabled[self.BLUE] and not GPIO.input(self.BLUE_PIN):
            blue_blocked = True
        if self.lanes_enabled[self.GREEN] and not GPIO.input(self.GREEN_PIN):
            green_blocked = True
        if self.lanes_enabled[self.YELLOW] and not GPIO.input(self.YELLOW_PIN):
            yellow_blocked = True
        if any([red_blocked, blue_blocked, green_blocked, yellow_blocked]):
            error_message = "Unable to start race.  Beam-break sensors on following lanes blocked: "
            if red_blocked:
                error_message += "\r\nRed"
            if blue_blocked:
                error_message += "\r\nBlue"
            if green_blocked:
                error_message += "\r\nGreen"
            if yellow_blocked:
                error_message += "\r\nYellow"
            error_message += "\r\nClear lanes, realign sensors, or disable blocked lanes to continue."
        else:
            error_message = None
        return error_message

if __name__ == '__main__':
    rm = RaceManager(test_mode=True)
    rm.configure_gpio()
    rm.close_gates()
    rm.start_race()