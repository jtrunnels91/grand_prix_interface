import RPi.GPIO as GPIO
import pigpio
servo = 12
servo2 = 13

pwm = pigpio.pi()
pwm.set_mode(servo, pigpio.OUTPUT)
pwm.set_mode(servo2, pigpio.OUTPUT)

BEAM_PIN = 26
#BEAM_PIN = 19
#BEAM_PIN = 6
#BEAM_PIN = 5

def break_beam_callback(channel):
    if GPIO.input(channel):
        print("beam unbroken")
        print(channel)
    else:
        print("beam broken")
        print(channel)

GPIO.setmode(GPIO.BCM)
GPIO.setup(BEAM_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(BEAM_PIN, GPIO.BOTH, callback=break_beam_callback)

message = input("Press enter to quit\n\n")
GPIO.cleanup()