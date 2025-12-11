# misc/enums.py
from micropython import const

class LED:
    ## LED Brightness
    NORMAL_BRIGHT = const(25)
    DIM_BRIGHT = const(250)
    MED_BRIGHT = const(500)
    BRIGHT_BRIGHT = const(900)

    ## Pulse durations
    SHORT_PULSE = const(250)
    LONG_PULSE = const(500)

    ## Pulse counts
    LORA_TX = const(1)
    LORA_RX = const(2)
    GPS_FIX = const(1)


class ICON:
    PASS = "\u2705"         # green checkmark
    FAIL = "\u274C"         # red X
    WAIT = "\u23F3"         # hourglass
    WARNING = "\u2757"      # red exclamation point
    UNKNOWN = "\u2753"      # red question mark
    SLEEP = chr(128164)     # zZz icon