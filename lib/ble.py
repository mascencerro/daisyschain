# ble.py

from misc.enums import ICON
import gc
from micropython import const
import uasyncio as asyncio
from device import Device

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_GATTS_READ_REQUEST = const(4)
_IRQ_MTU_EXCHANGED = const(21)

_BLE_MAX_CONNECT = const(1)
_BLE_MAX_RX_BYTES = const(512)

_BLE_COMMAND_BYTES = const(1)
_BLE_COMMAND_REBOOT = const(0xF0)
_BLE_COMMAND_RECONFIGURE = const(0xE0)

_TAG = "BLE"

class BLEModule:
    def __init__(self, device_instance: Device):
        import ubluetooth
        import ubinascii
        import ujson
        

        self._device = device_instance

        self._device.log(ICON.WAIT, " ", _TAG, ": Initializing...")

        self._debug_v = self._device.preferences.get('ble', {}).get('debug_v', False)
        self._enable = self._device.preferences.get('ble', {}).get('enable', True)

        self._ble = ubluetooth.BLE()
        self._ble.active(True)
        self._name = str(self._device.preferences.get('id', ('TX' if self._device.is_rover else 'RX') + ubinascii.hexlify(self._ble.config('mac')[1]).decode().upper()[-6:]) or 'ESP32_BLE')[:20]
        self._adv_payload = self._generate_advertise_payload(name=self._name)
        self._ble.config(gap_name=self._name, mtu=_BLE_MAX_RX_BYTES)
        self._ble.irq(self._irq)
        self._connections = set()

        asyncio.run(self._device.bus.emit('device.configure', {'ble.debug_v': self._debug_v, 'ble.enable': self._enable}))

        _BLE_SERVICE_UUID = ubluetooth.UUID('12345678-1234-5678-1234-56789abcdef0')
        _BLE_GPS_TX = (ubluetooth.UUID('12345678-1234-5678-1234-56789abcdef1'), ubluetooth.FLAG_NOTIFY,)
        _BLE_CONFIG_TX = (ubluetooth.UUID('12345678-1234-5678-1234-56789abcdef2'), ubluetooth.FLAG_READ,)
        _BLE_CONFIG_RX = (ubluetooth.UUID('12345678-1234-5678-1234-56789abcdef3'), ubluetooth.FLAG_WRITE | ubluetooth.FLAG_WRITE_NO_RESPONSE,)
        _BLE_COMMAND_RX = (ubluetooth.UUID('12345678-1234-5678-1234-56789abcdef4'), ubluetooth.FLAG_WRITE | ubluetooth.FLAG_WRITE_NO_RESPONSE,)

        _BLE_SERVICE = (_BLE_SERVICE_UUID, (_BLE_GPS_TX, _BLE_CONFIG_TX, _BLE_CONFIG_RX, _BLE_COMMAND_RX),)

        try:
            ((self._gps_tx_handle, self._config_tx_handle, self._config_rx_handle, self._command_rx_handle),) = self._ble.gatts_register_services((_BLE_SERVICE,))

            self._ble.gatts_set_buffer(self._config_rx_handle, _BLE_MAX_RX_BYTES, False)     # NOTE: to increase the config_rx_handle buffer size (default is 20 bytes)
            self._ble.gatts_set_buffer(self._command_rx_handle, _BLE_COMMAND_BYTES, False)

            self._conn_handle = None
            
            initial_preferences = ujson.dumps(self._device.preferences).encode('utf-8')
            self._ble.gatts_write(self._config_tx_handle, initial_preferences)
            
            self._advertising()
            self._device.log(ICON.PASS, " ", _TAG, ": Advertising as ", self._name)
            
            self._device.log(ICON.PASS, " ", _TAG, ": Module initialized\n")

        except Exception as e:
            self._ble = None
            self._device.log(ICON.FAIL, " ", _TAG, ": Could not initialize: ", e, "\n")

        del ubluetooth, ubinascii, ujson
        gc.collect()


    def get_ble_name(self):
        """
        Get BLE advertised name
        """
        return self._name


    def set_debug(self, debug: bool):
        """
        Enable/disable verbose debug message for BLE module
        """
        self._debug_v = bool(debug)


    async def send_gps_update_notification(self, data):
        """
        Notify BLE connections of updated GPS data received from Rover
        """
        try:
            if len(self._connections) > 0:
                for conn_handle in self._connections:
                    self._ble.gatts_notify(conn_handle, self._gps_tx_handle, data)
                    self._log("SEND -->: ", data)
                await asyncio.sleep(0)
        except Exception as e:
            self._log("Handled exception in BLE send: ", e)


    def _log(self, *args):
        if self._debug_v:
            self._device.log(_TAG + ": ", *args)


    def _irq(self, event, data):
        ## Connect event
        if event == _IRQ_CENTRAL_CONNECT:
            
            try:
                conn_handle, _, _ = data
                self._negotiate_mtu(conn_handle)
                self._connections.add(conn_handle)
                self._log("Connected: ", conn_handle)
                self._log("Current connections: ", self._connections)
            except Exception as e:
                if self._debug_v:
                    import sys
                    sys.print_exception(e, sys.stderr)
                self._log("Error accepting BLE connection: ", e)
            
            gc.collect()
            
            self._advertising()

        ## Disconnect event
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self._connections.discard(conn_handle)
            self._log("Disconnected: ", conn_handle)
            self._log("Remaining connections: ", self._connections if len(self._connections) > 0 else 'None')
            self._advertising()

        ## Write request
        elif event == _IRQ_GATTS_WRITE:
            if len(data) >= 2:
                _, attr_handle = data[0], data[1] 
            else:
                self._log("Write event with unexpected data length: ", len(data))
                return

            if attr_handle == self._command_rx_handle:
                try:
                    command = self._ble.gatts_read(self._command_rx_handle)
                    self._log("Received on command buffer: ", command)

                    if int.from_bytes(command) == _BLE_COMMAND_RECONFIGURE:
                        self._log("Configuration reset command received")
                        asyncio.create_task(self._device.bus.emit('device.reset_config'))

                    elif int.from_bytes(command) == _BLE_COMMAND_REBOOT:
                        self._log("Reboot command received")
                        asyncio.create_task(self._device.bus.emit('device.reboot'))
                    
                    else:
                        self._log("Unrecognized command code received: ", command)
                
                except Exception as e:
                    self._log("Could not read command buffer: ", e)

            elif attr_handle == self._config_rx_handle:
                try:
                    buffer = self._ble.gatts_read(self._config_rx_handle)
                    
                    asyncio.create_task(self._process_config_data(buffer))

                except Exception as e:
                    self._log("Error handling GATTS read: ", e)

            else:
                self._log("Write to unexpected handle: ", attr_handle)
        
        ## Read request
        elif event == _IRQ_GATTS_READ_REQUEST:
            if len(data) == 4:
                ## Standard expected unpacking
                conn_handle, attr_handle, offset, max_len = data
            elif len(data) == 2:
                ## Handling for observed non-standard case
                conn_handle, attr_handle = data
            else:
                self._log("Unexpected data length for READ_REQUEST: ", len(data))
            
            if attr_handle == self._config_tx_handle:
                self._log("Received READ request for config (Handle: ", attr_handle, ")")
                self._update_config_characteristic()

        ## MTU negotiation complete
        elif event == _IRQ_MTU_EXCHANGED:
            conn_handle, mtu = data
            self._log("Conn handle: ", conn_handle, " | MTU exchanged: ", mtu)
                

    def _negotiate_mtu(self, conn_handle):
        """
        Negotiate minimum MTU with server
        """
        if hasattr(self._ble, 'gattc_exchange_mtu'):
            try:
                self._ble.gattc_exchange_mtu(conn_handle)
            except Exception as e:
                self._log("Failed to set MTU: ", e)          


    async def _process_config_data(self, buffer):
        """
        Parse and process configuration data received
        """
        try:
            import misc.thistothat as thistothat
            
            config_data, err = thistothat.is_json(buffer)
            if config_data:
                self._log("Received configuration change: ", config_data)
                asyncio.create_task(self._device.bus.emit('device.configure', config_data))

            else:
                self._log(err, " | Data received: ", buffer)
            
            del thistothat
            gc.collect()
        
        except ValueError:
                self._log("Received invalid JSON for configuration.")
        except Exception as e:
            if self._debug_v:
                import sys
                sys.print_exception(e, sys.stderr)
            self._log("GATTS_WRITE error during config processing: ", e)
    
    
    def _update_config_characteristic(self):
        """
        Writes the current device config to the READ characteristic
        """
        try:
            import ujson
            if self._ble:
                config_data = ujson.dumps(self._device.preferences).encode('utf-8')
                self._ble.gatts_write(self._config_tx_handle, config_data)
            
            del ujson
            gc.collect()
        except Exception as e:
            self._log("Configuration characteristic update failed: ", e)
    
    
    def _generate_advertise_payload(self, name=None):
        name_bytes = name.encode('utf-8')
        payload = bytearray()

        # Flags field
        payload += bytearray([
            0x02,   # Length of this data
            0x01,   # Flags data type value
            0x06    # Flags value (General Discoverable Mode, BR/EDR not supported)
        ])

        # Complete Local Name field
        payload += bytearray([
            len(name_bytes) + 1,  # Length of name + 1 for type byte
            0x09  # Complete Local Name data type
        ]) + name_bytes

        return payload


    def _advertising(self):
        import utime
        utime.sleep_ms(100)

        try:
            self._ble.gap_advertise(None)

            if len(self._connections) < _BLE_MAX_CONNECT:
                self._log((_BLE_MAX_CONNECT - len(self._connections)), " connections available, continuing advertisement.")
                self._ble.gap_advertise(100_000, adv_data=self._adv_payload)
            else:
                self._log("Connections at maximum: ", _BLE_MAX_CONNECT, " stopping advertisement.")

        except Exception as e:
            self._log("Failed to restart advertising: ", e)
        
        gc.collect()


