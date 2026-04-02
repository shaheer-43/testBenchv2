import time
import lgpio

# Define ESC pin
ESC_PIN = 12

# Open GPIO chip
h = lgpio.gpiochip_open(0)

# Claim the pin as output
lgpio.gpio_claim_output(h, ESC_PIN)

THROTTLE_CUT = True

def set_throttle(throttle_percent):
    """
    Set throttle percentage (0–100)
    Maps to ESC pulse width 1000–2000 µs
    """
    pulse_width = int((throttle_percent / 100) * 1000) + 1000
    lgpio.tx_servo(h, ESC_PIN, pulse_width)

def print_with_timestamp(message):
    timestamp = int(time.time() * 1000)
    print(f"[{timestamp} ms] {message}")

# Initialize ESC
set_throttle(0)
time.sleep(2)

def cut_throttle():
    global THROTTLE_CUT
    set_throttle(0)
    THROTTLE_CUT = True

def restart_throttle():
    global THROTTLE_CUT
    if THROTTLE_CUT:
        set_throttle(100)
        THROTTLE_CUT = False
