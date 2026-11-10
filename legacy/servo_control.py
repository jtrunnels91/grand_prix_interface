import RPi.GPIO as GPIO
servo_pin = 13

GPIO.setmode(GPIO.BCM)
GPIO.setup(servo_pin, GPIO.OUT)
p = GPIO.PWM(servo_pin, 50)
