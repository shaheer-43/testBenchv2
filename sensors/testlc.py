import time
import RPi.GPIO as GPIO
from hx711 import HX711

# GPIO setup
GPIO.setmode(GPIO.BCM)

DOUT_PIN = 13
SCK_PIN = 19

# Initialize HX711
hx = HX711(
    dout_pin=DOUT_PIN,
    pd_sck_pin=SCK_PIN
)
cal=4
hx.set_scale_ratio(cal)


print("===================================")
print(" HX711 Single Load Cell Test")
print("===================================")
print()
print("GPIO DOUT : 5")
print("GPIO SCK  : 6")
print()
print("Remove all load from the load cell.")
print("Starting zero/tare in 3 seconds...")
time.sleep(3)

# Zero the load cell
hx.zero()

print("Zero complete.")
print()
print("Apply/remove load and watch the value.")
print("Press CTRL+C to stop.")
print()

try:
    while True:
        weight = hx.get_weight_mean(readings=5)

        if weight is False:
            print("ERROR: HX711 returned False")
        else:
            print(f"Weight: {weight:10.2f}")

        time.sleep(0.2)

except KeyboardInterrupt:
    print("\nStopping test...")

finally:
    GPIO.cleanup()
    print("GPIO cleanup complete.")
