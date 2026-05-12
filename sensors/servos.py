import time
from rpi_hardware_pwm import HardwarePWM

# =============================================================================
# Raspberry Pi 5 Hardware PWM Pin Mapping (rpi-hardware-pwm library):
#   Channel 0 → GPIO 12
#   Channel 1 → GPIO 13
#   Channel 2 → GPIO 18
#   Channel 3 → GPIO 19
#
#   THROTTLE SERVO  → Channel 2 → GPIO 18
#   CHOKE SERVO     → Channel 3 → GPIO 19
#
# /boot/firmware/config.txt must include:
#   dtoverlay=pwm-2chan,pin=18,func=2,pin2=19,func2=2
# =============================================================================

# --- Tunable throttle pulse range (adjust on physical bench) ---
THROTTLE_MIN_US = 900   # Pulse width at 0% throttle
THROTTLE_MAX_US = 1350  # Pulse width at 100% throttle

# --- Choke servo pulse range ---
CHOKE_OPEN_US  = 2000
CHOKE_CLOSE_US = 1000

# --- PWM carrier frequency (standard 50 Hz for hobby servos) ---
SERVO_HZ  = 50
PERIOD_US = 1_000_000 / SERVO_HZ  # 20,000 µs

# --- Hardware PWM initialisation (chip=0 for Pi 5 after overlay) ---
throttle_pwm = HardwarePWM(pwm_channel=2, hz=SERVO_HZ, chip=0)  # GPIO 18
choke_pwm    = HardwarePWM(pwm_channel=3, hz=SERVO_HZ, chip=0)  # GPIO 19

throttle_pwm.start(0)
choke_pwm.start(0)

# --- Killed flag: when True, set_throttle_percent is a no-op ---
_killed = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _us_to_duty(pulse_us):
    """Convert a pulse width in µs to a duty-cycle percentage."""
    return (pulse_us / PERIOD_US) * 100.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_throttle_percent(percent):
    """
    Set the throttle servo to a position between 0% and 100%.
    Maps linearly from THROTTLE_MIN_US (0%) to THROTTLE_MAX_US (100%).
    Ignored silently if the engine has been killed.
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
    """
    Hard-kill: drive throttle to 0% (minimum pulse) and lock out
    any further set_throttle_percent calls until reset.
    """
    global _killed
    _killed = True
    throttle_pwm.change_duty_cycle(_us_to_duty(THROTTLE_MIN_US))
    print("Throttle KILLED → 0% (minimum pulse)")


def reset_kill():
    """
    Clear the kill flag so set_throttle_percent works again.
    Call this before re-enabling the throttle slider after a kill.
    """
    global _killed
    _killed = False
    print("Kill flag cleared — throttle re-enabled.")


def toggle_choke(is_open):
    """Open or close the choke servo."""
    pulse_us = CHOKE_OPEN_US if is_open else CHOKE_CLOSE_US
    choke_pwm.change_duty_cycle(_us_to_duty(pulse_us))
    print(f"Choke {'opened' if is_open else 'closed'} ({pulse_us} µs)")


def cleanup():
    """Stop all PWM outputs cleanly on exit."""
    throttle_pwm.stop()
    choke_pwm.stop()
    print("Servo PWM stopped.")