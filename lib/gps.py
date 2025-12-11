# gps.py

import machine
from micropython import const
import uasyncio as asyncio
from misc.enums import ICON, LED
import misc.thistothat as thistothat
from utime import sleep_ms, mktime
import config_manager
from device import Device
import random

## Seconds between Jan 1, 1970 (UNIX Epoch) - Jan 1, 1980 (GPS Epoch)
_EPOCH_OFFSET = const(946684800)

## Mock coordinate base (for bench testing)
_MOCK_LAT = 36.1569
_MOCK_LON = -95.9915

_TAG = "GPS"

class GPSModule:
    """
    GPS module class
    """
    def __init__(self, device_instance: Device):
        from hardware.micropyGPS import MicropyGPS

        self._device = device_instance
        
        self._device.log(ICON.WAIT, " ", _TAG, ": Initializing...")

        self._debug_v = self._device.preferences.get('gps', {}).get('debug_v', False)
        self._enable = self._device.preferences.get('gps', {}).get('enable', True)
        self.mock = self._device.preferences.get('gps', {}).get('mock', False)
        self._status = {'lat': 0, 'lon': 0, 'sat': 0, 'ut': 0, 'alt': 0, 'gh': 0}
        self._last_lat = 0.0
        self._last_lon = 0.0
        self._last_ut = 0

        UART_BUS_ID = config_manager.board_config.get('UART_BUS_ID')
        GPS_TX_PIN = config_manager.board_config.get('GPS_TX_PIN')
        GPS_RX_PIN = config_manager.board_config.get('GPS_RX_PIN')
        GPS_BAUDRATE = config_manager.board_config.get('GPS_BAUDRATE')
        
        self._gps_gpio_pwr = config_manager.board_config.get('GPS_GPIO_CTRL')
        
        ## Assuming Heltec LoRa v4 is using L76K
        if config_manager.board == 'heltecwifilora32v4':
            self._gps_gpio_pwr = machine.Signal(self._gps_gpio_pwr, invert=True)
            self._gps_gpio_rst = config_manager.board_config.get('GPS_GPIO_RST')
            self._gps_gpio_rst.on()
                    
        self.data = None

        self._gps_gpio_pwr.on()
        sleep_ms(50)

        # Placeholder config option to implement DMS coordinates
        self._decimal_coords = self._device.preferences.get('gps', {}).get('decimal_coords', True)
        
        asyncio.run(self._device.bus.emit('device.configure', {'gps.decimal_coords': self._decimal_coords,
                                                               'gps.enable': self._enable,
                                                               'gps.debug_v': self._debug_v,
                                                               'gps.mock': self.mock}))        
        
        self._uart = None
        self._gps = MicropyGPS()
        try:
            self._uart = machine.UART(UART_BUS_ID, baudrate=GPS_BAUDRATE, tx=GPS_TX_PIN, rx=GPS_RX_PIN)
            self._device.log(ICON.PASS, " ", _TAG, ": Initialized.\n")
        except Exception as e:
            self._uart = None
            self._device.log(ICON.FAIL, " ", _TAG, ": Could not initialize: ", e, "\n")
    
        ## Cleanup
        del MicropyGPS
        import gc
        gc.collect()
    
    
    def _log(self, *args):
        if self._debug_v:
            self._device.log(_TAG + ": ", *args)
    

    def _update(self):
        """
        Read characters from UART and feed to microGPS for parsing
        """
        if self._uart and self._uart.any():
            try:
                data = self._uart.read()
                if data:
                    for char in data:
                        self._gps.update(chr(char))
            except Exception as e:
                self._log("Error parsing GPS data: ", e)

    
    def _get_coords_simple(self):
        """
        Return GPS tuple (latitude, longitude)
        """
        if self._gps.fix_time is not None:
            latitude, longitude = thistothat.gps_tuple_to_decimal(self._gps.latitude, self._gps.longitude)
            return (latitude, longitude)
    
    
    def _get_unix_timestamp(self, time, date):
        """
        Return UNIX timestamp (1/1/1970 00:00:00)
        """
        try:
            td_tuple = (date[2] + 2000,
                        date[1],
                        date[0],
                        time[0],
                        time[1],
                        int(time[2]),
                        0,
                        0)
            return mktime(td_tuple) + _EPOCH_OFFSET
        except Exception as e:
            self._log("Invalid timestamp to process: ", e)
        
        return 0
    
    
    def _get_coords_dict(self):
        """
        Return GPS data as dictionary
        """
        if self._decimal_coords:
            latitude, longitude = thistothat.gps_tuple_to_decimal(self._gps.latitude, self._gps.longitude)

            self.data = {
                "lat": latitude,
                "lon": longitude,
                "sat": self._gps.satellites_in_view,
                # "is_fixed": self._gps.fix_time is not None,
                # "ts": self._gps.timestamp,
                # "dt": self._gps.date,
                "ut": self._get_unix_timestamp(self._gps.timestamp, self._gps.date),
                # "l_off": self._gps.local_offset,
                # "spd": self._gps.speed,
                # "dir": self._gps.course,
                "alt": self._gps.altitude,
                "gh": self._gps.geoid_height
            }

            self._log("rx<- : ", self.data)

            if latitude != 0 and longitude != 0:
                ## Store fix data for times we lose fix
                self._last_lat = self.data['lat']
                self._last_lon = self.data['lon']
                self._last_ut = self.data['ut']

            else:
                if self.mock:
                    ## NOTE: This section only provides mock coordinates for testing
                    self.data['lat'] = _MOCK_LAT + float(random.randrange(0, 100) / 1_000_000)
                    self.data['lon'] = _MOCK_LON + float(random.randrange(0, 100) / 1_000_000)
                    self._log("Could not get accurate coordinates, providing mock coordinates for testing. (", self.data['lat'], ", ", self.data['lon'], ")")

                else:
                    ## If we had a fix but lost it, provide last fix data
                    if self._last_lat != 0 and self._last_lon != 0:
                        self.data['lat'] = self._last_lat
                        self.data['lon'] = self._last_lon
                        self.data['ut'] = self._last_ut

                    else:
                        self._log("Waiting on fix.")
        
        else:
            self._log("DMS coordinate support not implemented")
    
    
    def set_debug(self, debug: bool):
        """
        Enable/disable verbose debug message for GPS module
        """
        self._debug_v = bool(debug)

    
    async def run(self):
        """
        Async GPS poller continuously reads from UART and emit fix events
        """
        while True:
            self._update()
            # Only emit fix if we have enough data
            if self.mock or (self._gps.fix_time is not None and self._gps.satellites_in_view > 0):
                prev_coords = (self._last_lat, self._last_lon)
                self._get_coords_dict()
                if self.data and self.data.get('lat') and self.data.get('lon'):
                    current_coords = (self.data.get('lat'), self.data.get('lon'))
                    coords_changed = False
                    self._log("Obtained fix: (", self.data.get('lat'), ", ", self.data.get('lon'), ")")
                    if current_coords != prev_coords:
                        coords_changed = True
                    await self._device.bus.emit('gps.fix', coords_changed)
                ## Pulse LED on fix
                # asyncio.create_task(self._device.bus.emit('device.led.pulse', count=LED.GPS_FIX, duration=LED.SHORT_PULSE, brightness=LED.DIM_BRIGHT))
                
                else:
                    self._log("Attempting to obtain fix")
            else:
                self._log("Searching for satellite")
                
            await asyncio.sleep_ms(950)
    
    
    def gps_toggle(self):
        """
        Turn GPS module on/off
        """
        self._log("Toggling GPS module ", 'OFF' if self._gps_gpio_pwr.value() else 'ON')
        self._gps_gpio_pwr.value(not self._gps_gpio_pwr.value())


    def gps_pwr_status(self):
        """
        Get current GPS enabled/disabled status
        """
        return self._gps_gpio_pwr.value()

