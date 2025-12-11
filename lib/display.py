# display.py

from micropython import const
from misc.enums import ICON
import utime
import uasyncio as asyncio
from device import Device

_TAG = "Display"

class Display:
    """
    Display module class
    """

    def __init__(self, device_instance: Device):
        self._device = device_instance
        
        self._device.log(ICON.WAIT, " ", _TAG, ": Initializing...")

        self._load_preferences()

        self._oled = None
        self._gfx = None

        if self._enable:
            self._initialize_hardware()
        
        if not self._oled:
            self._set_display_stubs()
        
        self._device.log(ICON.PASS if self._oled else ICON.FAIL, " ", _TAG, ": Initialization complete. Display ", 'Active' if self._oled else 'Disabled')


    def _initialize_hardware(self):
        """
        Initialize display hardware (if enabled in preferences)
        """
        from machine import SoftI2C, Pin
        from hardware.ssd1306 import SSD1306_I2C
        from hardware.gfx import GFX
        import config_manager

        try:
            ## Pin setup
            I2C_SCL_PIN = config_manager.board_config.get('I2C_SCL_PIN')
            I2C_SDA_PIN = config_manager.board_config.get('I2C_SDA_PIN')
            OLED_RESET = config_manager.board_config.get('OLED_RESET')
            OLED_VEXT = config_manager.board_config.get('OLED_VEXT')

            I2C_SDA_PIN.init(Pin.OPEN_DRAIN, pull=Pin.PULL_UP)
            I2C_SCL_PIN.init(Pin.OPEN_DRAIN, pull=Pin.PULL_UP)
            # set backlight to 0 for bright or 1 for off
            OLED_VEXT.value(0)

            _i2c = SoftI2C(sda=I2C_SDA_PIN, scl=I2C_SCL_PIN)

            devices = _i2c.scan()
            if not devices:
                raise OSError(f"No I2C devices found.")
            
            if 0x3c not in devices:
                raise OSError(f"SSD1306 (0x3c) not found on I2C bus.")
            
            ## Reset OLED (fix random display of static)
            for i in range(0, 2):
                OLED_RESET.value(i % 2)
                utime.sleep_ms(10)

            self.DISPLAY_WIDTH = config_manager.board_config.get('DISPLAY_WIDTH')
            self.DISPLAY_HEIGHT = config_manager.board_config.get('DISPLAY_HEIGHT')

            self._oled = SSD1306_I2C(self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT, _i2c)
            self._gfx = GFX(self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT, self._oled.pixel)

            self._BLACK = const(0)
            self._WHITE = const(1)

            self._MARGIN = const(1)
            self._LINE_WIDTH = const(1)
            self._FONT_WIDTH = const(8)
            self._FONT_HEIGHT = const(8)

            self._heartbeat_ico = ['Oo.', 'oOo', '.oO']
            self._heartbeat_i = 0
            self._heartbeat_dir = 1

            self.show_text_centered("Starting up...")
            self._device.log(ICON.PASS, " ", _TAG, ": SSD1306 display initialized.\n")

        except Exception as e:
            self._device.log(ICON.FAIL, " ", _TAG, ": Hardware initialization failed: ", e)
            self._oled = None
        
        ## Cleanup
        del SoftI2C, Pin, SSD1306_I2C, GFX, config_manager
        import gc
        gc.collect()
    

    def _set_display_stubs(self):
        """
        Assign None to display objects and set stubs for all display methods
        """
        self._oled = None
        self._gfx = None

        ## Define stub functions for missing/disabled/inoperable display
        self.update, self.show_text = self._no_display_stub, self._no_display_stub
        self.clear, self._divider_line = self._no_display_stub, self._no_display_stub
        self.show_ui_base, self.heartbeat = self._no_display_stub, self._no_display_stub
        self.show_header, self.show_data_labels = self._no_display_stub, self._no_display_stub
        self.clear_data, self.show_data = self._no_display_stub, self._no_display_stub
        self.goodnight, self.show_text_centered = self._no_display_stub, self._no_display_stub
        self.set_debug = self._no_display_stub


    def _log(self, *args):
        if self._debug_v:
            self._device.log(_TAG + ": ", *args)


    def _load_preferences(self):
        """
        Load stored display preferences
        """
        self._debug_v = self._device.preferences.get('display', {}).get('debug_v', False)
        self._enable = self._device.preferences.get('display', {}).get('enable', True)
        self._brightness = int(self._device.preferences.get('display', {}).get('brightness', 100))
        self._contrast = int(self._device.preferences.get('display', {}).get('contrast', 100))
        
        asyncio.run(self._device.bus.emit('device.configure', {'display.debug_v': self._debug_v,
                                                               'display.enable': self._enable,
                                                               'display.brightness': self._brightness,
                                                               'display.contrast': self._contrast}))


    def _no_display_stub(self, *args, **kwargs):
        """
        Stub function for device with no display
        """
        pass


    def _divider_line(self):
        """
        Display section divider
        """
        self._gfx.line(0, self._FONT_HEIGHT + self._MARGIN, self.DISPLAY_WIDTH, self._FONT_HEIGHT + self._MARGIN, self._WHITE)


    def set_debug(self, debug: bool):
        """
        Enable/disable verbose debug message for Display module
        """
        self._debug_v = bool(debug)


    ## Basic display control functions
    def update(self):
        """
        Update display from framebuffer (no screen clearing)
        """
        self._oled.write_framebuf()

    def show_text(self, text, x=0, y=0):
        """
        Clear display and show text
        """
        self._oled.fill(0)
        self._oled.text(text, x, y)
        self.update()

    def show_text_centered(self, text):
        """
        Clear display and show text centered
        """
        self._oled.fill(0)
        x = int((self.DISPLAY_WIDTH / 2) - ((len(text) / 2) * self._FONT_WIDTH))
        y = int((self.DISPLAY_HEIGHT / 2) - (self._FONT_HEIGHT / 2))
        self._oled.text(text, x, y)
        self.update()

    def clear(self):
        """
        Clear display
        """
        self._oled.fill(0)
        self.update()


###########################################################
    # MARGIN = 1
    # LINE_WIDTH = 1
    # FONT_WIDTH = 6
    # FONT_HEIGHT = 8
    # DISPLAY_W = 128
    # DISPLAY_H = 64

    def goodnight(self, i):
        """
        Show message on display before entering deepsleep
        """
        self.clear()
        self._oled.text(f"goodnight", int((self.DISPLAY_WIDTH / 2) - 40), int((self.DISPLAY_HEIGHT / 2) - 4))
        self._oled.text(str(i), int((self.DISPLAY_WIDTH / 2)) - 4, int((self.DISPLAY_HEIGHT / 2)) + 14)
        self.update()


    def show_ui_base(self, labels):
        """
        Update display with base layout
        """
        self.clear()
        self._divider_line()
        self.show_data_labels(labels)
        self.heartbeat()


    ##### Heartbeat (top right ~24x8  - 3 char)
    # CHARS = 3
    # x0 = DISPLAYWIDTH - (FONT_WIDTH * CHARS)
    # xE = DISPLAYWIDTH
    # y0 = 0
    # yE = y0 + FONT_HEIGHT + MARGIN

    def heartbeat(self):
        """
        Device heartbeat indicator
        """
        CHARS = 3
        x0 = self.DISPLAY_WIDTH - (self._FONT_WIDTH * CHARS)
        xE = self.DISPLAY_WIDTH
        y0 = 0
        yE = y0 + self._FONT_HEIGHT + self._MARGIN
        
        ## Clear heartbeat section
        self._gfx.fill_rect(x0, y0, xE, yE, self._BLACK)
        
        ## Adjust heartbeat_ico index (increment/deincrement)
        if (self._heartbeat_i + self._heartbeat_dir < 0) or (self._heartbeat_i + self._heartbeat_dir > 2):
            self._heartbeat_dir *= -1
        self._heartbeat_i += self._heartbeat_dir
        
        self._oled.text(self._heartbeat_ico[self._heartbeat_i], x0, y0, self._WHITE)


    ##### Header (top left ~104x8 - 16 char)
    # CHARS = 16
    # x0 = 0
    # xE = FONT_WIDTH * CHARS
    # y0 = 0
    # yE = FONT_HEIGHT

    def show_header(self, text):
        """
        Update display header
        """
        CHARS = 13
        x0 = 0
        xE = self._FONT_WIDTH * CHARS
        y0 = 0
        yE = self._FONT_HEIGHT
        self._gfx.fill_rect(x0, y0, xE, yE, self._BLACK)
        self._oled.text(f"{text}", x0, y0, self._WHITE)


    ##### Status (bottom)
    ### Label (left side ~40px x ~ - 5 char)
    # CHARS = 5
    # LINES = 5
    # LINE_SPACE = 3
    # x0 = 0
    # xE = FONT_WIDTH * CHARS
    # y0 = FONT_HEIGHT + MARGIN + LINE_WIDTH + MARGIN
    # yE = DISPLAY_HEIGHT

    def show_data_labels(self, labels):
        """
        Update display information labels
        """
        CHARS = 5
        LINES = 5
        LINE_SPACE = 3
        x0 = 0
        xE = self._FONT_WIDTH * CHARS
        y0 = self._FONT_HEIGHT + self._MARGIN + 1 + self._MARGIN
        yE = (self._FONT_HEIGHT * LINES) + (self._MARGIN + (2 * LINES) + self._MARGIN)
        self._gfx.fill_rect(x0, y0, xE, yE, self._BLACK)
        for idx, label in enumerate(labels):
            if label:
                self._oled.text(label, x0, y0 + self._MARGIN + (idx * self._FONT_HEIGHT) + (idx * LINE_SPACE), self._WHITE)



    ### Data (right side ~88px wide - 16 char)
    # CHARS = 16
    # LINES = 5
    # LINE_SPACE = 3
    # x0 = DISPLAY_WIDTH - (FONT_WIDTH * CHARS) - MARGIN
    # xE = DISPLAY_WIDTH
    # y0 = FONT_HEIGHT + MARGIN + LINE_WIDTH + MARGIN
    # yE = DISPLAY_HEIGHT

    def clear_data(self):
        """
        Clear display information section
        """
        CHARS = 11
        LINES = 5
        LINE_SPACE = 3
        x0 = self.DISPLAY_WIDTH - (self._FONT_WIDTH * CHARS - self._MARGIN)
        xE = self.DISPLAY_WIDTH - x0
        y0 = self._FONT_HEIGHT + self._MARGIN + 1 + self._MARGIN
        yE = (self._FONT_HEIGHT * LINES) + (LINE_SPACE * (LINES - 1))
        self._gfx.fill_rect(x0, y0, xE, yE, self._BLACK)


    def show_data(self, data):
        """
        Update display information section
        """
        CHARS = 16
        LINES = 5
        LINE_SPACE = 3
        x0 = self.DISPLAY_WIDTH - (self._FONT_WIDTH * CHARS - self._MARGIN)
        xE = self.DISPLAY_WIDTH - x0
        y0 = self._FONT_HEIGHT + self._MARGIN + 1 + self._MARGIN
        yE = (self._FONT_HEIGHT * LINES) + (LINE_SPACE * (LINES - 1))
        self.clear_data()
        for idx, line in enumerate(data):
            if line:
                x0 = xE - (len(str(line)) * self._FONT_WIDTH)
                self._oled.text(str(line), x0, y0 + self._MARGIN + (idx * self._FONT_HEIGHT) + (idx * LINE_SPACE), self._WHITE)

