import RPi.GPIO as GPIO
import time

servoPIN = 12
servoPIN2 = 13
GPIO.setmode(GPIO.BCM)
GPIO.setup(servoPIN, GPIO.OUT)
GPIO.setup(servoPIN2, GPIO.OUT)

p = GPIO.PWM(servoPIN, 50) # GPIO 17 for PWM with 50Hz
p2 = GPIO.PWM(servoPIN2, 50) # GPIO 17 for PWM with 50Hz
p.start(2.5) # Initialization
p2.start(2.5) # Initialization
try:
  while True:
    p.ChangeDutyCycle(2.5)
    p2.ChangeDutyCycle(2.5)
    time.sleep(1)
    p.ChangeDutyCycle(6)
    p2.ChangeDutyCycle(6)
    time.sleep(2)
    p.ChangeDutyCycle(12.5)
    p2.ChangeDutyCycle(12.5)
    time.sleep(1)
except KeyboardInterrupt:
  p2.stop()
  p.stop()
  GPIO.cleanup()