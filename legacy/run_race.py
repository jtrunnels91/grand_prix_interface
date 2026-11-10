import RPi.GPIO as GPIO
import pigpio
import datetime as dt
import time
import random

class RaceManager:
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
            test_mode=False
    ):
        self.LEFT_SERVO_PIN = LEFT_SERVO_PIN
        self.RIGHT_SERVO_PIN = RIGHT_SERVO_PIN
        self.RED_PIN = RED_PIN
        self.BLUE_PIN = BLUE_PIN
        self.GREEN_PIN = GREEN_PIN
        self.YELLOW_PIN = YELLOW_PIN

        self.SERVO_CLOSE = SERVO_CLOSE
        self.SERVO_OPEN = SERVO_OPEN

        self.gpio_configured = False

        self.race_in_progress = False
        self.race_start_time = None

        self.LEFT_SERVO_CLOSED = 500
        self.LEFT_SERVO_OPEN = 1500

        self.RIGHT_SERVO_CLOSED = 2500
        self.RIGHT_SERVO_OPEN = 1500

        self.lane_finish_times = {
            "RED": None,
            "BLUE": None,
            "GREEN": None,
            "YELLOW": None
        }
        self.lanes_enabled = {
            "RED": red_enabled,
            "BLUE": blue_enabled,
            "GREEN": green_enabled,
            "YELLOW": yellow_enabled
        }

        self.test_mode = test_mode

    def enable_disable_lanes(
        self,
        red_enabled=True,
        blue_enabled=True,
        green_enabled=True,
        yellow_enabled=True
    ):
        self.lanes_enabled = {
            "RED": red_enabled,
            "BLUE": blue_enabled,
            "GREEN": green_enabled,
            "YELLOW": yellow_enabled
        }

    def __del__(self):
        print("Cleaning up GPIO")
        GPIO.cleanup()

    def configure_gpio(self):
        GPIO.setmode(GPIO.BCM)

        if self.lanes_enabled["RED"]:
            GPIO.setup(self.RED_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                self.RED_PIN,
                GPIO.FALLING,
                callback=self.break_beam_callback
            )

        if self.lanes_enabled["BLUE"]:
            GPIO.setup(self.BLUE_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                self.BLUE_PIN,
                GPIO.FALLING,
                callback=self.break_beam_callback
            )
        if self.lanes_enabled["GREEN"]:
            GPIO.setup(self.GREEN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                self.GREEN_PIN,
                GPIO.FALLING,
                callback=self.break_beam_callback
            )
        if self.lanes_enabled["YELLOW"]:
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

    def start_race(self):
        if self.race_in_progress:
            raise ValueError(
                "Cannot start new race while race still in progress."
            )
        if not self.gpio_configured:
            raise ValueError(
                "Must configure GPIO first"
            )
        self.lane_finish_times = {
            lane: (None if enabled else False) for lane, enabled in self.lanes_enabled.items()
        }

        lanes_blocked = self.check_lanes_blocked()
        if lanes_blocked is not None:
            raise ValueError(lanes_blocked)

        self.open_gates()
        self.race_start_time = dt.datetime.now()
        self.race_in_progress = True

        if self.test_mode is True:
            self.lane_finish_times = {
                lane: (dt.timedelta(seconds=random.uniform(10,60)) if enabled else False) for lane, enabled in self.lanes_enabled.items()
            }

            self.end_race()

        return

    def close_gates(self):
        self.pwm.set_servo_pulsewidth(self.LEFT_SERVO_PIN, self.LEFT_SERVO_CLOSED)
        self.pwm.set_servo_pulsewidth(self.RIGHT_SERVO_PIN, self.RIGHT_SERVO_CLOSED)
    def open_gates(self):
        self.pwm.set_servo_pulsewidth(self.LEFT_SERVO_PIN, self.LEFT_SERVO_OPEN)
        self.pwm.set_servo_pulsewidth(self.RIGHT_SERVO_PIN, self.RIGHT_SERVO_OPEN)
    def end_race(self):
        self.race_in_progress = False
        self.close_gates()
        self.print_results()
    def print_results(self):
        print("RACE RESULTS:")
        for key, value in self.lane_finish_times.items():
            if value:
                print(str(key) + ": " + str(value.total_seconds()))

    def break_beam_callback(self, channel):
        if self.race_in_progress and not GPIO.input(channel):
            if channel == self.RED_PIN:
                lane = "RED"
            elif channel == self.BLUE_PIN:
                lane = "BLUE"
            elif channel == self.GREEN_PIN:
                lane = "GREEN"
            elif channel == self.YELLOW_PIN:
                lane = "YELLOW"
            if self.lane_finish_times[lane] is None:
                t_current = dt.datetime.now()
                self.lane_finish_times[lane] = (
                    t_current - self.race_start_time
                )

            if all([d is not None for d in self.lane_finish_times.values()]):

                self.end_race()

    def check_lanes_blocked(self):
        red_blocked = False
        blue_blocked = False
        green_blocked = False
        yellow_blocked = False
        # Check that all four lanes are clear
        if self.lanes_enabled['RED'] and not GPIO.input(self.RED_PIN):
            red_blocked = True
        if self.lanes_enabled['BLUE'] and not GPIO.input(self.BLUE_PIN):
            blue_blocked = True
        if self.lanes_enabled['GREEN'] and not GPIO.input(self.GREEN_PIN):
            green_blocked = True
        if self.lanes_enabled['YELLOW'] and not GPIO.input(self.YELLOW_PIN):
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