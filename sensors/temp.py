import time
import math
import board
import busio

from adafruit_ads1x15 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn


# ============================================================
# CONFIGURATION
# ============================================================

VCC = 5.0
R_FIXED = 9870.0

# Calibration point
T0_C = 26.0
T0_K = T0_C + 273.15

# NTC resistance at calibration temperature
R0 = 8800.0

# KY-013 / 10k NTC beta
BETA = 3950.0


# ============================================================
# ADS1115 INITIALIZATION
# ============================================================

i2c = busio.I2C(board.SCL, board.SDA)

ads = ADS1115(i2c)

# ±6.144 V range
ads.gain = 2 / 3

# KY-013 connected to ADS1115 A0
chan = AnalogIn(ads, 0)


# ============================================================
# TEMPERATURE READING
# ============================================================

def get_temperature(samples=32):
    """
    Read the KY-013 temperature sensor.

    Returns:
        float: Temperature in °C
    """

    # Average ADC samples
    total = 0.0

    for _ in range(samples):
        total += chan.value
        time.sleep(0.005)

    raw = total / samples

    # Read ADC voltage
    voltage = chan.voltage

    # Safety checks
    if voltage >= VCC:
        raise ValueError(
            f"KY-013 voltage too high: {voltage:.3f} V"
        )

    if voltage <= 0:
        raise ValueError(
            f"KY-013 voltage too low: {voltage:.3f} V"
        )

    # --------------------------------------------------------
    # Calculate NTC resistance
    #
    #       5V
    #        |
    #       NTC
    #        |
    #        +---- Signal
    #        |
    #      9.87k
    #        |
    #       GND
    #
    # R_NTC = R_FIXED * Vout / (VCC - Vout)
    # --------------------------------------------------------

    resistance = R_FIXED * voltage / (VCC - voltage)

    # --------------------------------------------------------
    # Beta equation
    # --------------------------------------------------------

    temperature_k = 1.0 / (
        (1.0 / T0_K)
        + (math.log(resistance / R0) / BETA)
    )

    temperature_c = temperature_k - 273.15

    return temperature_c


# ============================================================
# OPTIONAL: RETURN SENSOR DATA
# ============================================================

def read_temperature():
    samples = 32
    total = 0.0

    for _ in range(samples):
        total += chan.value
        time.sleep(0.005)

    raw = total / samples
    voltage = chan.voltage

    if voltage <= 0 or voltage >= VCC:
        return None

    resistance = R_FIXED * voltage / (VCC - voltage)

    temperature_k = 1.0 / (
        (1.0 / T0_K)
        + (math.log(resistance / R0) / BETA)
    )

    return temperature_k - 273.15
