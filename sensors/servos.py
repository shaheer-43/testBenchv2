import time
from rpi_hardware_pwm import HardwarePWM
 
# =============================================================================
# Raspberry Pi 5 Hardware PWM Pin Mapping (rpi-hardware-pwm library):
#   Channel 0 → GPIO 12
#   Channel 1 → GPIO 13
#   Channel 2 → GPIO 18
#   Channel 3 → GPIO 19
#
# IMPORTANT: GPIO 23 does NOT support hardware PWM on the Pi 5.
# Reassigned pins:
#   SERVO1 (Main servo)    → Channel 2 → GPIO 18
#   SERVO2 (Choke servo)   → Channel 3 → GPIO 19
#
# Make sure your /boot/firmware/config.txt includes:
#   dtoverlay=pwm-2chan,pin=18,func=2,pin2=19,func2=2
# Then reboot before running this script.
# =============================================================================
 
# Servo PWM frequency (standard for most servos)
SERVO_HZ = 50  # 50 Hz → 20 ms period
 
# Pulse width range in microseconds
SERVO_MIN_US = 500   # 0°
SERVO_MAX_US = 2500  # 180°
 
# Period in microseconds for 50 Hz
PERIOD_US = 1_000_000 / SERVO_HZ  # 20,000 µs
 
# Initialize hardware PWM channels
# chip=2 is required for Pi 5 (RP1 chip); use chip=0 for older Pi models
servo1_pwm = HardwarePWM(pwm_channel=2, hz=SERVO_HZ, chip=0)  # GPIO 18
servo2_pwm = HardwarePWM(pwm_channel=3, hz=SERVO_HZ, chip=0)  # GPIO 19
 
servo1_pwm.start(0)
servo2_pwm.start(0)
 
 
def angle_to_duty_cycle(angle):
    """Convert an angle (0–180°) to a duty cycle percentage for 50 Hz PWM."""
    pulse_us = SERVO_MIN_US + (angle / 180.0) * (SERVO_MAX_US - SERVO_MIN_US)
    duty_cycle = (pulse_us / PERIOD_US) * 100.0
    return duty_cycle
 
 
def set_servo_angle(gpio_pin, angle):
    """Accept a GPIO pin number (matching original API) and set servo angle."""
    pwm_map = {
        18: servo1_pwm,
        19: servo2_pwm,
    }
    pwm_instance = pwm_map.get(gpio_pin)
    if pwm_instance is None:
        print(f"No PWM instance found for GPIO {gpio_pin}")
        return
    duty = angle_to_duty_cycle(angle)
    pwm_instance.change_duty_cycle(duty)
    print(f"Servo on GPIO {gpio_pin} set to {angle}°")
 
 
def toggle_choke(is_open):
    """Open or close the choke (controls SERVO1 on GPIO 18)."""
    if is_open:
        set_servo_angle(servo1_pwm, "GPIO 18 (Main/Choke)", 90)
        print("Choke opened.")
    else:
        set_servo_angle(servo1_pwm, "GPIO 18 (Main/Choke)", 0)
        print("Choke closed.")
 
 
def cleanup():
    """Stop PWM outputs cleanly on exit."""
    servo1_pwm.stop()
    servo2_pwm.stop()
    print("Servo PWM stopped.")
