# device.py

import uasyncio as asyncio
from micropython import alloc_emergency_exception_buf, const
import machine
import utime
import config_manager as conf
from misc.enums import ICON, LED

_PRESSED = const(0)
_RELEASED = const(1)

_BUTTON_BUMP = const(250)
_BUTTON_SHORT = const(1000)
_BUTTON_LONG = const(4000)
_BUTTON_SLEEP = const(5000)

alloc_emergency_exception_buf(100)

_TAG = "Device"

class Device:
    """
    Combines and initializes all peripherals
    """
    def __init__(self, preferences):
        from ble import BLEModule
        from display import Display
        from event import EventBus
        from lora import LoRaModule
        from gps import GPSModule
        
        _DEBUG_V = conf.board_config.get('DEBUG_V')
        _SECRET = conf.board_config.get('SECRET')
        
        self.batt_read = conf.board_config.get('BATT_READ')
        self.button = conf.board_config.get('BUTTON')
        self.led = conf.board_config.get('LED')
        
        self.led.duty(LED.NORMAL_BRIGHT)

        ''' Load user preferences if available or set defaults '''
        self.preferences = preferences
        
        self.is_rover = preferences.get('is_rover', False)      # Default to base
        self.id = preferences.get('id', None)                   # ID will be generated during BLE init
        self.debug_v = preferences.get('debug_v', _DEBUG_V)
        self.event_debug_v = preferences.get('event_debug_v', False)    # Event Bus verbose debugging messages (spammy)
        self.secret = preferences.get('secret', _SECRET)
        self.wd = preferences.get('wd', True)
        
        self.log(ICON.WAIT, " ", self.preferences.get('id', 'Unnamed device'), " starting up...\n")
        
        ''' Bring it all up'''
        self.bus = EventBus(self)
        self.bus.subscribe('device.configure', self._update_config)
        self.bus.subscribe('device.reboot', self._restart)
        self.bus.subscribe('device.reset_config', self._reset_config)
        self.bus.subscribe('device.sleep', self._sleep)
        self.bus.subscribe('device.led.pulse', self._pulse_led)

        self.ble = BLEModule(self)
        self.lora = LoRaModule(self)
        self.gps = GPSModule(self) if self.is_rover else None
        self.display = Display(self)   # NOTE: Display needs to be last so framebuffer doesn't fragment heap in inconvenient places

        if self.id is None:
            self.id = self.ble.get_ble_name()
        
        asyncio.create_task(self.bus.emit('device.configure', {'is_rover': self.is_rover,
                                                       'id': self.id,
                                                       'debug_v': self.debug_v,
                                                       'secret': self.secret,
                                                       'wd': self.wd}))

        self.shutdown = False

        self.log(ICON.PASS, " ", preferences.get('id'), " start-up complete.\n")
        
        ## Cleanup
        del BLEModule, Display, EventBus, GPSModule, LoRaModule
        import gc
        gc.collect()


    def _log(self, *args):
        if self.debug_v:
            self.log(_TAG + ":", *args)


    async def _shutdown(self, message='shutdown'):
        """
        Device shutdown
        """
        self.shutdown = True
        pause = const(3)
        self._log("Device ", message, " in:")
        await asyncio.sleep_ms(200)
        self.bus.subscribers.clear()
        self.bus.clean_tasks()
        for i in range(pause, 0, -1):
            self._log(i)
            self.display.show_text_centered(f"{message} in {i}")
            await asyncio.sleep_ms(1000)
    

    async def _restart(self):
        """
        Device restart
        """
        await self._shutdown('restart')
        await asyncio.sleep_ms(200)
        self.display.show_text_centered("Restarting")
        self._log("Restarting")
        machine.soft_reset()


    async def _sleep(self):
        """
        Device sleep
        """
        await self._shutdown('sleep')
        asyncio.sleep_ms(200)
        if self.gps and self.gps.gps_pwr_status():
            self.gps.gps_toggle()
            asyncio.sleep_ms(50)
        self.log("goodnight ", ICON.SLEEP)
        self.display.show_text_centered(f"Going to sleep")
        utime.sleep_ms(2000)
        machine.deepsleep()


    def _reset_config(self):
        """
        Device call to reset configuration to default
        """
        conf.reset_preferences()
        asyncio.run(self.bus.emit('device.reboot'))


    def _update_config(self, new_config_data):
        """
        Device call to update configuration
        """
        conf.update_preferences(self.preferences, new_config_data)


    async def _pulse_led(self, count=2, duration=500, brightness=900):
        """
        Pulse LED `pulse_count` times over `pulse_time` ms
        """
        segment = int((duration / count) / 2)
        for _ in range(count):
            self.led.duty(brightness)
            await asyncio.sleep_ms(segment)
            self.led.duty(LED.NORMAL_BRIGHT)
            await asyncio.sleep_ms(segment)


    def log(self, *args):
        """
        Output messages to serial
        """
        print(*args, sep='')


    def set_debug(self, debug: bool):
        """
        Enable/disable verbose debugging output for device messages
        """
        self._debug_v = bool(debug)


    async def check_button(self):
        """
        Check for button press events
        """
        while True:
            if self.button.value() == _PRESSED:
                await asyncio.sleep_ms(30)
                if self.button.value() == _PRESSED:
                    start = utime.ticks_ms()
                    while self.button.value() == _PRESSED:
                        await asyncio.sleep_ms(30)
                        elapsed = utime.ticks_diff(utime.ticks_ms(), start)
                        
                        if elapsed >= _BUTTON_SLEEP:
                            asyncio.create_task(self.bus.emit('device.sleep'))
                            break

                    ## Break out of block if sleep triggered
                    if elapsed >= _BUTTON_SLEEP:
                        break

                    elapsed = utime.ticks_diff(utime.ticks_ms(), start)
                    if elapsed < _BUTTON_BUMP:
                        if self.debug_v:
                            self._log("Bump press detected")
                        await self.bus.emit('button.bump')
                    elif elapsed > _BUTTON_SHORT and elapsed < _BUTTON_LONG:
                        if self.debug_v:
                            self._log("Long press detected")
                        await self.bus.emit('button.long')
            await asyncio.sleep_ms(100)

