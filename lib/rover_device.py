# rover_device.py

import uasyncio as asyncio
import utime
import misc.thistothat as thistothat
import device
import gc

_TAG = "Main"

_NO_FIX_MSG = ["Searching", "for", "GPS", "..."]

class RoverDeviceHandler:
    def __init__(self, device_instance: device.Device):
        self._device = device_instance

        self.data_labels = (" LAT:",
                            " LON:",
                            " SAT:",
                            " ToA:",
                            None)

        self.data_data = [None, None, None, None, None]

        self._device.display.show_ui_base(labels=self.data_labels)
        self._update_display()
        
        self._device.bus.subscribe('button.bump', self._button_bump)
        self._device.bus.subscribe('button.long', self._button_long)
        self._device.bus.subscribe('lora.rx', self._lora_rx)
        self._device.bus.subscribe('lora.tx', self._lora_tx)
        self._device.bus.subscribe('gps.fix', self._gps_fix)


    def _log(self, *args):
        if self._device.debug_v:
            self._device.log(_TAG + ": ", *args)
    
    
    def _button_bump(self):
        """
        Handle bump (<250ms) button press/release
        """
        self._log("Bump press recieved")

        
    def _button_long(self):
        """
        Handle long (>250ms, <4000ms) button press/release
        """
        self._log("Long press recieved")


    async def _lora_rx(self, message: bytes, rssi: int, toa: float):
        """
        Handle and process recieved LoRa message
        """
        pass

    
    def _lora_tx(self):
        """
        Handle LoRa transmission completion
        """
        pass


    async def _gps_fix(self, coords_changed: bool=False):
        """
        Handle GPS status update
        """
        try:
            message_toa = await self._device.lora.send_message(self._device.gps.data)
            if message_toa and coords_changed:
                self._update_display(message_toa)
        except Exception as e:
            self._log("Failed to transmit GPS data: ", e)

    
    
    def _update_display(self, message_toa: int=0):
        """
        Update rover (tracker) display
        
        *DOES NOT* push display buffer to display
        """
        if self._device.display is not None:
            if self._device.gps.data:
                latitude = self._device.gps.data.get('lat')
                latitude = thistothat.simplify_display_coordinate(latitude)
                
                longitude = self._device.gps.data.get('lon')
                longitude = thistothat.simplify_display_coordinate(longitude)

                satellites = self._device.gps.data.get('sat')
                if satellites is None: satellites = "N/A"

                self.data_data[0] = latitude
                self.data_data[1] = longitude
                self.data_data[2] = satellites
                self.data_data[3] = str(message_toa) + "ms"
                self._device.display.show_data(self.data_data)
                
            else:
                self._device.display.show_data(_NO_FIX_MSG)
        else:
            pass

    
    async def run(self):
        """
        Event loop (base device)
        """
        asyncio.create_task(self._device.gps.run())
        
        while not self._device.shutdown:
            loop_start_tick = utime.ticks_ms()
            self._device.display.heartbeat()
            self._device.display.show_header(self._device.id)
            self._device.display.update()
            
            ## Attempt to keep uniform loop cycle time to 250ms, or min 1ms if run over
            await asyncio.sleep_ms(max(1, 250 - (utime.ticks_diff(utime.ticks_ms(), loop_start_tick))))

            