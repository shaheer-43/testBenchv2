import time
import threading
import lgpio

# --- ESC GPIO pin (starter motor) ---
ESC_PIN = 12

# --- ESC pulse range ---
ESC_MIN_US = 1000   # 0%   throttle
ESC_MAX_US = 2000   # 100% throttle

# --- RPM threshold at which the starter cuts off automatically ---
STARTER_RPM_THRESHOLD = 3000

# Open GPIO chip and claim pin
h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(h, ESC_PIN)

# Internal state
_starter_thread = None
_starter_stop_event = threading.Event()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _set_esc_percent(percent):
    """Drive the ESC at a given percentage (0–100). Not kill-gated."""
    percent = max(0.0, min(100.0, float(percent)))
    pulse_us = int(ESC_MIN_US + (percent / 100.0) * (ESC_MAX_US - ESC_MIN_US))
    lgpio.tx_servo(h, ESC_PIN, pulse_us)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def cut_throttle():
    """Immediately cut the ESC to 0."""
    _set_esc_percent(0)


def run_starter(rpm_callback, on_complete):
    """
    Run the starter motor at 100% ESC in a background thread.
    Polls rpm_callback() every 200 ms until RPM >= STARTER_RPM_THRESHOLD,
    then cuts the starter and calls on_complete() on the main thread.

    rpm_callback : callable → float   — returns current RPM
    on_complete  : callable           — called (thread-safe via root.after)
                                        when starter cuts out
    """
    global _starter_thread, _starter_stop_event

    # Safety: stop any existing starter run
    stop_starter()

    _starter_stop_event.clear()

    def _worker():
        _set_esc_percent(100)
        print("Starter running at 100%...")

        while not _starter_stop_event.is_set():
            try:
                rpm = rpm_callback()
            except Exception as e:
                print(f"RPM read error during start: {e}")
                rpm = 0

            print(f"  Starter polling — RPM: {rpm:.0f}")

            if rpm >= STARTER_RPM_THRESHOLD:
                break

            time.sleep(0.2)

        _set_esc_percent(0)
        print(f"Starter cut — RPM threshold ({STARTER_RPM_THRESHOLD}) reached or stop requested.")
        try:
            on_complete()
        except Exception as e:
            print(f"Starter on_complete error: {e}")

    _starter_thread = threading.Thread(target=_worker, daemon=True)
    _starter_thread.start()


def stop_starter():
    """Force-stop the starter thread and cut the ESC immediately."""
    global _starter_thread
    _starter_stop_event.set()
    if _starter_thread and _starter_thread.is_alive():
        _starter_thread.join(timeout=1.0)
    _set_esc_percent(0)
    _starter_thread = None


def cleanup():
    """Stop starter thread and silence ESC on exit."""
    stop_starter()
    lgpio.gpiochip_close(h)
    print("ESC cleaned up.")