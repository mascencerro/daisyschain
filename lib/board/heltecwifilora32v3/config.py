# heltecwifilora32v3/config.py

from machine import Pin, PWM
from micropython import const

"""
    Configuration for Heltec WiFi LoRa 32 V3 (3.2)
    
    Pin assignments -------
    General:
        LED      = 35      (white led)
        PRG_BTN  = 0       (user button)
    
    OLED:
        RST_PIN  = 21      (gpio 21)
        SDA_PIN  = 17      (gpio 17)
        SCL_PIN  = 18      (gpio 18)
        VEXT_PIN = 36      (backlight) (low to enable)
        
    LoRa:
        SPI      = 1
        CLK      = 9       (LoRa_SCK)
        MOSI     = 10      (LoRa_MOSI)
        MISO     = 11      (LoRa_MISO)
        CS       = 8       (LoRa_NSS)
        IRQ      = 14      (DIO1)
        RST      = 12      (LoRa_RST)
        GPIO     = 13      (LoRa_BUSY)
    
    GPS (GT-U7):
        CTRL     = 34
        TX       = 38
        RX       = 39

"""


LOW = const(0)
HIGH = const(1)

# OLED pin assignments for SSD1306 (I2C)
I2C_BUS_ID = const(0)
I2C_SCL_PIN = Pin(18, Pin.OPEN_DRAIN)
I2C_SDA_PIN = Pin(17, Pin.OPEN_DRAIN)
OLED_RESET = Pin(21, Pin.OUT, value=HIGH)
OLED_VEXT = Pin(36, Pin.OUT, Pin.PULL_UP)
DISPLAY_WIDTH = const(128)
DISPLAY_HEIGHT = const(64)


# LoRa pin assignments for SX126x (SPI)
SPI_BUS_ID = const(1)
SPI_SCK_PIN = Pin(9)
SPI_MOSI_PIN = Pin(10)
SPI_MISO_PIN = Pin(11)
LORA_NSS_PIN = Pin(8)
LORA_RESET_PIN = Pin(12)
LORA_GPIO_PIN = Pin(13)
LORA_DIO1_PIN = Pin(14, Pin.IN, Pin.PULL_DOWN)
DEFAULT_LORA_FREQ = const(902.5)
DEFAULT_LORA_BANDWIDTH = 250.0
DEFAULT_LORA_SF = const(7)
DEFAULT_LORA_TX_PWR = const(5)
LORA_SEND_LIMIT = const(5)      # seconds

# GPS pin assignments for GT-U7 (UART)
UART_BUS_ID = const(2)
GPS_GPIO_CTRL = Pin(34, Pin.OUT)
GPS_TX_PIN = Pin(38)
GPS_RX_PIN = Pin(39)
GPS_BAUDRATE = const(9600)

# Other device config
BUTTON = Pin(0, Pin.IN, Pin.PULL_UP)
LED_PWM_FREQ = const(1000)
LED = PWM(Pin(35, Pin.OUT), freq=LED_PWM_FREQ)
BATT_READ = Pin(1, Pin.OUT)
BATT_READ_CTRL = Pin(37, Pin.OUT, value=LOW)

####
# Default config options
SECRET = "01234567"

WATCHDOG = const(30000)    # watchdog timer (ms)

####
# Debug messages
DEBUG_V = True


#################################################################