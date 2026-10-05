import time
import lgpio
from rpi_hardware_pwm import HardwarePWM

# =============================================================================
# Raspberry Pi 5 Servo Pin Assignment:
#
#   THROTTLE SERVO → Hardware PWM → GPIO 18 (channel 2)
#   CHOKE SERVO    → Software PWM → GPIO 19 (lgpio)
#
# GPIO 19 is freed from hardware PWM so it can coexist with hx2 load cell
# on GPIO 13/19. The choke only moves to two positions (open/closed) so
# software PWM jitter is irrelevant.
#
# /boot/firmware/config.txt must include (for throttle only):
#   dtoverlay=pwm-2chan,pin=18,func=2,pin2=19,func2=2
#   (pin2/func2 line is harmless to leave but GPIO 19 PWM won't be used)
# =============================================================================

# --- Tunable throttle pulse range (adjust on physical bench) ---
THROTTLE_MIN_US = 800    # Pulse width at 0% throttle
THROTTLE_MAX_US = 1500   # Pulse width at 100% throttle

# --- Choke servo pulse range ---
CHOKE_OPEN_US  = 2000
CHOKE_CLOSE_US = 1000

# --- PWM frequency ---
SERVO_HZ  = 50
PERIOD_US = 1_000_000 / SERVO_HZ  # 20,000 µs

# --- Choke GPIO pin ---
CHOKE_PIN = 19

# ---------------------------------------------------------------------------
# Throttle: Hardware PWM via rpi-hardware-pwm (GPIO 18, channel 2)
# ---------------------------------------------------------------------------
throttle_pwm = HardwarePWM(pwm_channel=2, hz=SERVO_HZ, chip=0)
throttle_pwm.start(0)

# --- Killed flag ---
_killed = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _us_to_duty(pulse_us):
    """Convert pulse width in µs to duty cycle percentage for hardware PWM."""
    return (pulse_us / PERIOD_US) * 100.0


def _send_choke_pulse(pulse_us):
    """
    Claim GPIO 19, send one servo pulse, then release the pin.
    This avoids holding the pin open and conflicting with hx2 load cell.
    """
    h = lgpio.gpiochip_open(0)
    try:
        lgpio.gpio_claim_output(h, CHOKE_PIN)
        lgpio.tx_servo(h, CHOKE_PIN, pulse_us)
        time.sleep(0.5)  # Hold pulse long enough for servo to move
        lgpio.tx_servo(h, CHOKE_PIN, 0)  # Stop PWM signal
    finally:
        lgpio.gpiochip_close(h)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_throttle_percent(percent):
    """
    Set throttle servo position (0–100%).
    Maps linearly: 0% = THROTTLE_MIN_US, 100% = THROTTLE_MAX_US.
    No-op if engine is killed.
    """
    global _killed
    if _killed:
        print("Throttle command ignored — engine is killed.")
        return
    percent = max(0.0, min(100.0, float(percent)))
    pulse_us = THROTTLE_MIN_US + (percent / 100.0) * (THROTTLE_MAX_US - THROTTLE_MIN_US)
    throttle_pwm.change_duty_cycle(_us_to_duty(pulse_us))
    print(f"Throttle → {percent:.1f}%  ({pulse_us:.0f} µs)")


def kill_throttle():
    """Drive throttle to minimum pulse and lock out further commands."""
    global _killed
    _killed = True
    throttle_pwm.change_duty_cycle(_us_to_duty(THROTTLE_MIN_US))
    print("Throttle KILLED → 0% (minimum pulse)")


def reset_kill():
    """Clear kill flag so set_throttle_percent works again."""
    global _killed
    _killed = False
    print("Kill flag cleared — throttle re-enabled.")


def toggle_choke(is_open):
    """
    Open or close the choke servo.
    Claims GPIO 19 only for the duration of the pulse, then releases it
    so the hx2 load cell can use the pin freely between choke operations.
    Runs in a background thread so it doesn't block the GUI.
    """
    pulse_us = CHOKE_OPEN_US if is_open else CHOKE_CLOSE_US
    state_str = 'opened' if is_open else 'closed'

    def _pulse():
        _send_choke_pulse(pulse_us)
        print(f"Choke {state_str} ({pulse_us} µs)")

    import threading
    threading.Thread(target=_pulse, daemon=True).start()


def cleanup():
    """Stop throttle PWM cleanly on exit."""
    throttle_pwm.stop()
    print("Servo PWM stopped.")
