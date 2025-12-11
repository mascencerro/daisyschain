# lora.py

from utime import sleep_ms
from misc.enums import ICON, LED
import misc.thistothat as thistothat
import utime
from device import Device
import uasyncio as asyncio
import ujson

_TAG = "LoRa"

class LoRaModule:
    """
    LoRa module class
    """

    def __init__(self, device_instance: Device):
        from hardware.micropySX126X.sx1262 import SX1262
        import config_manager
        from misc.queue import Queue
        
        self._device = device_instance
        
        self._device.log(ICON.WAIT, " ", _TAG, ": Initializing...")

        self._debug_v = self._device.preferences.get('lora', {}).get('debug_v', False)
               
        SPI_BUS_ID = config_manager.board_config.get('SPI_BUS_ID')
        SPI_SCK_PIN = config_manager.board_config.get('SPI_SCK_PIN')
        SPI_MOSI_PIN = config_manager.board_config.get('SPI_MOSI_PIN')
        SPI_MISO_PIN = config_manager.board_config.get('SPI_MISO_PIN')

        LORA_NSS_PIN = config_manager.board_config.get('LORA_NSS_PIN')
        LORA_RESET_PIN = config_manager.board_config.get('LORA_RESET_PIN')
        LORA_GPIO_PIN = config_manager.board_config.get('LORA_GPIO_PIN')
        LORA_DIO1_PIN = config_manager.board_config.get('LORA_DIO1_PIN')

        ## NOTE: Heltec WiFi LoRa V4 needs these HIGH to tx/rx full power ¯\_(ツ)_/¯
        if config_manager.board == 'heltecwifilora32v4':
            self._pa_power = config_manager.board_config.get('LORA_PA_POWER_PIN')
            self._pa_en = config_manager.board_config.get('LORA_PA_EN_PIN')
            self._pa_tx_en = config_manager.board_config.get('LORA_PA_TX_EN_PIN')
            
            self._log("Enabling LoRa PA")

            self._pa_en.on()
            if self._device.is_rover:
                self._log("Enabling LoRa TX PA")
                self._pa_tx_en.on()

        DEFAULT_LORA_BANDWIDTH = config_manager.board_config.get('DEFAULT_LORA_BANDWIDTH')
        DEFAULT_LORA_FREQ = config_manager.board_config.get('DEFAULT_LORA_FREQ')
        DEFAULT_LORA_SF = config_manager.board_config.get('DEFAULT_LORA_SF')
        DEFAULT_LORA_TX_PWR = config_manager.board_config.get('DEFAULT_LORA_TX_PWR')

        LORA_SEND_LIMIT = config_manager.board_config.get('LORA_SEND_LIMIT')
        
        self._queue = Queue()
        
        self._last_send = utime.ticks_ms()
        self._send_lock = False

        self._lora = None
           
        self._freq = float(self._device.preferences.get('lora', {}).get('freq', DEFAULT_LORA_FREQ))
        self._bw = int(self._device.preferences.get('lora', {}).get('bw', DEFAULT_LORA_BANDWIDTH))
        self._sf = int(self._device.preferences.get('lora', {}).get('sf', DEFAULT_LORA_SF))
        self._tx = int(self._device.preferences.get('lora', {}).get('tx', DEFAULT_LORA_TX_PWR))
        self._rate_limit = int(self._device.preferences.get('lora', {}).get('rate_limit', LORA_SEND_LIMIT))
        
        asyncio.run(self._device.bus.emit('device.configure', {'lora.freq': self._freq,
                                                               'lora.bw': self._bw,
                                                               'lora.sf': self._sf,
                                                               'lora.tx': self._tx,
                                                               'lora.rate_limit': self._rate_limit,
                                                               'lora.debug_v': self._debug_v,
                                                               'lora.tx_pa': hasattr(self, '_pa_tx_en')
                                                               }))

        try:
            self._lora = SX1262(spi_bus=SPI_BUS_ID,
                               clk=SPI_SCK_PIN,
                               mosi=SPI_MOSI_PIN,
                               miso=SPI_MISO_PIN,
                               cs=LORA_NSS_PIN,
                               irq=LORA_DIO1_PIN,
                               rst=LORA_RESET_PIN,
                               gpio=LORA_GPIO_PIN)

            self._lora.begin(freq=self._freq,
                            bw=self._bw,
                            sf=self._sf,
                            cr=8,
                            syncWord=0x1424,
                            power=self._tx,
                            currentLimit=60,
                            preambleLength=8,
                            implicit=False,
                            implicitLen=0xFF,
                            crcOn=True,
                            txIq=False,
                            tcxoVoltage=1.7,
                            useRegulatorLDO=False,
                            blocking=True,
                            txPa=hasattr(self, '_pa_tx_en'))
            
            self._lora.setBlockingCallback(False, self._rx_tx_cb)

            self._device.log(ICON.PASS, " ", _TAG, ": SX126X module initialized.\n")

        except Exception as e:
            self._lora = None
            self._device.log(ICON.FAIL, " ", _TAG, ": Could not initialize: ", e, "\n")

        ## Cleanup
        del SX1262, config_manager, Queue
        import gc
        gc.collect()
        

    def _log(self, *args):
        if self._debug_v:
            self._device.log(_TAG + ": ", *args)
    

    def _rx_tx_cb(self, events):
        """
        LoRa RX/TX (non-blocking) callback
        """
        ## Handle rx events
        if events & self._lora.RX_DONE:
            packet, err = self._lora.recv()
            if not err:
                try:
                    self._queue.put_nowait((packet, self._lora.getRSSI(), self._lora.getTimeOnAir(len(packet))))
                except Exception as e:
                    self._log("LoRa packet processing error: ", e)
            else:
                self._log("LoRa packet receive error: ", err)

        ## Handle tx events
        if events & self._lora.TX_DONE:
            self._log("Lora packet sent")
            # self.device.bus.emit('lora.tx', None)
            pass

    
    def set_debug(self, debug: bool):
        """
        Enable/disable verbose debug message for LoRa module
        """
        self._debug_v = bool(debug)


    async def check_incoming_queue(self):
        """
        Loop function for periodically checking LoRa message queue
        
        Emit event on lora.rx for each incoming message read
        """
        while True:
            queue_item = await self._queue.get()
            
            if queue_item is None:
                self._log("Empty or None queue item, skipping")
                continue
            
            if not isinstance(queue_item, (tuple, list)) or len(queue_item) != 3:
                self._log("Malformed queue item: ", queue_item)
                continue
            
            packet, rssi, toa = queue_item
            try:
                self._log("rx<- len: ", len(packet), " msg: ", packet)
                asyncio.create_task(self._device.bus.emit('device.led.pulse', count=LED.LORA_RX, duration=LED.SHORT_PULSE, brightness=LED.MED_BRIGHT))
                await self._device.bus.emit('lora.rx', packet, rssi, toa)
            except Exception as e:
                self._log("Error emitting lora.rx event: ", e)


    async def send_message(self, message):
        """
        LoRa SEND (non-blocking)
        """
        ## Throttle to lora._rate_limit
        if utime.ticks_diff(utime.ticks_ms(), self._last_send) < (self._rate_limit * 1000):
            return None
        
        if self._lora and not self._send_lock:
            try:
                self._send_lock = True
                if isinstance(message, dict):
                    message['id'] = self._device.id
                    
                lora_message = thistothat.message_pack(ujson.dumps(message), self._device.secret)
                self._lora.send(lora_message)
                asyncio.create_task(self._device.bus.emit('device.led.pulse', count=LED.LORA_TX, duration=LED.SHORT_PULSE, brightness=LED.MED_BRIGHT))
                await self._device.bus.emit('lora.tx')
                
                self._log("tx-> len: ", len(lora_message), " msg: '", lora_message, "'")

                self._last_send = utime.ticks_ms()
                return self._get_toa(len(lora_message))
            
            except Exception as e:
                self._log("Send failure: ", e)
            
            finally:
                self._send_lock = False
        
        else:
            self._log("Send blocked: send_lock=", self._send_lock)
        
        return None

            
    def _get_toa(self, message_len: int):
        """
        Get Time-on-Air of LoRa message of `message_len` rounded to 1 decimal position
        """
        return round(self._lora.getTimeOnAir(message_len) / 1000, 1)


