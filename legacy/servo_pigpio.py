import pigpio
import time

servo = 12
servo2 = 13

pwm = pigpio.pi()
pwm.set_mode(servo, pigpio.OUTPUT)
pwm.set_mode(servo2, pigpio.OUTPUT)

#pwm.set_PWM_frequency(servo, 50)
#pwm.set_PWM_range(servo, 20000) # 1,000,000 / 50 = 20,000us for 100% duty cycle

while True:
    pwm.set_servo_pulsewidth(servo, 500)
    pwm.set_servo_pulsewidth(servo2, 500)
    time.sleep(1)
    pwm.set_servo_pulsewidth(servo, 1500)
    pwm.set_servo_pulsewidth(servo2, 1500)
    time.sleep(1)
    pwm.set_servo_pulsewidth(servo, 2500)
    pwm.set_servo_pulsewidth(servo2, 2500)
    time.sleep(2)

pwm.set_servo_pulsewidth(servo, 0)
pwm.set_servo_pulsewidth(servo2, 0)