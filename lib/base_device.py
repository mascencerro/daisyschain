# base_device.py

import uasyncio as asyncio
from micropython import const
import utime
import ujson
import misc.thistothat as thistothat
import device
import tracking

_ROVERS_SAVE_INTERVAL = const(300_000)     # 5 minutes

_TAG = "Main"

_NO_SIGNAL_MSG = ["Waiting", "for", "signal", "..."]

class BaseDeviceHandler:
    def __init__(self, device_instance: device.Device):
        self._device = device_instance
        self.tracked_rover = None
        self.saved_rovers_tick = 0

        self.data_labels = ("  ID:",
                            " LAT:",
                            " LON:",
                            " SAT:",
                            "RSSI:")

        self.data_data = [None, None, None, None, None]

        tracking.load_rovers()
        self._device.display.show_ui_base(labels=self.data_labels)
        self._update_display()
        
        self._device.bus.subscribe('button.bump', self._button_bump)
        self._device.bus.subscribe('button.long', self._button_long)
        if self._device.lora is not None:
            self._device.bus.subscribe('lora.rx', self._lora_rx)


    def _log(self, *args):
        if self._device.debug_v:
            self._device.log(_TAG + ": ", *args)


    def _track_next(self):
        """
        Increment to and display tracking information for next tracked rover.
        """
        if len(tracking.Rover.list_rovers()) > 0:
            tracking.Rover.current_rover_index = (tracking.Rover.current_rover_index + 1) % len(tracking.Rover.list_rovers())
            self.tracked_rover = tracking.Rover._rovers.get(tracking.Rover.list_rovers()[tracking.Rover.current_rover_index])
            self._log("Switching tracking to: ", self.tracked_rover.id)
            if self._device.display is not None:
                self._update_display()
                self._device.display.update()


    def _button_bump(self):
        """
        Handle short (<250ms) button press/release
        """
        self._track_next()


    def _button_long(self):
        """
        Handle long (>250ms, <4000ms) button press/release
        """
        if self.tracked_rover is None:
            self._log("No rover currently tracked to untrack")
            return
        
        self._log("Removing ", self.tracked_rover.id, " from tracking")
        
        tracking.Rover.untrack_rover(self.tracked_rover.id)
        tracking.save_rovers()
        self._track_next()


    async def _lora_rx(self, message: bytes, rssi: int, toa: float):
        """
        Handle and process recieved LoRa message
        """
        
        try:
            tracked_data, err = thistothat.is_json(thistothat.message_unpack(message, self._device.secret))
            
            if tracked_data is not None:
                ## Make sure data at least has 'id' before proceeding
                if tracked_data.get('id') is None:
                    return
                
                rover_id = tracked_data.get('id')
                
                ## Update/Save tracked data as Rover
                if tracking.Rover.get_rover(rover_id):
                    tracking.Rover.get_rover(rover_id).update(tracked_data, rssi, toa)
                    self._log("Updating existing rover with ID: ", rover_id)
                else:
                    tracking.Rover(tracked_data, rssi, toa)
                    self._log("Created new rover with ID: ", rover_id)
                    tracking.save_rovers()
                
                ## Set rover being tracked if none already tracked
                if self.tracked_rover is None:
                    self.tracked_rover = tracking.Rover._rovers.get(rover_id)
                    
                    ## Align index with selected rover
                    if rover_id in tracking.Rover.list_rovers():
                        tracking.Rover.current_rover_index = tracking.Rover.list_rovers().index(rover_id)
                    
                    self._log("Automatically setting tracking to rover: ", self.tracked_rover.id)
                
                if self._device.ble is not None:
                    tracked_data['rssi'] = rssi
                    tracked_data['toa'] = toa
                    await asyncio.create_task(self._device.ble.send_gps_update_notification(ujson.dumps(tracked_data).encode()))

                self._log("Tracked data processed: ", tracked_data)
            
            else:
                self._log(err, " | Data received: ", message)
                        
        except Exception as e:
            self._log("Failed to decode message: ", e)
            
        self._update_display()


    def _lora_tx(self):
        """
        Handle LoRa transmission completion
        """
        pass


    def _update_display(self):
        """
        Update base (receiver) display
        
        *DOES NOT* push display buffer to display
        """
        if self._device.display is not None:
            if self.tracked_rover is not None:                
                latitude = self.tracked_rover.gps_data.get('lat')
                latitude = thistothat.simplify_display_coordinate(latitude)
                
                longitude = self.tracked_rover.gps_data.get('lon')
                longitude = thistothat.simplify_display_coordinate(longitude)
                
                satellites = self.tracked_rover.gps_data.get('sat')
                if satellites is None: satellites = "N/A"
                
                self.data_data[0] = self.tracked_rover.id
                self.data_data[1] = latitude
                self.data_data[2] = longitude
                self.data_data[3] = satellites
                self.data_data[4] = str(self.tracked_rover.last_rssi) + "db"
                self._device.display.show_data(self.data_data)
                
            else:
                self._device.display.show_data(_NO_SIGNAL_MSG)
        else:
            pass


    async def run(self):
        """
        Event loop (base device)
        """
        while not self._device.shutdown:
            loop_start_tick = utime.ticks_ms()
            self._device.display.heartbeat()
            self._device.display.show_header(f": {int((utime.ticks_ms() - self.tracked_rover.last_track) / 1000) if self.tracked_rover else 'N/A'} :")
            self._device.display.update()
            
            ## Update stored rovers file
            if utime.ticks_diff(utime.ticks_ms(), self.saved_rovers_tick) > _ROVERS_SAVE_INTERVAL:
                self._device.log("")
                self._device.log("---------- Current Rovers -----------")
                for rover_id, rover_object in tracking.Rover._rovers.items():
                    yyyy, mm, dd, hh, mm, ss = thistothat.TimeConverter(unix_epoch=rover_object.gps_data.get('ut')).time_tuple[:6]
                    self._device.log("ID: ", rover_id, " GPS Data: ", rover_object.gps_data, " Last Track: ", dd, "/", mm, "/", yyyy, " ", hh, ":", mm, ":", ss, "UTC")
                self._device.log("-------------------------------------")
                self._device.log("")
                tracking.save_rovers()
                self.saved_rovers_tick = utime.ticks_ms()

            ## Attempt to keep uniform loop cycle time to 250ms, or min 1ms if run over
            await asyncio.sleep_ms(max(1, 250 - (utime.ticks_diff(utime.ticks_ms(), loop_start_tick))))

