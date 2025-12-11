# misc/thistothat.py

import binascii
import ujson
import utime

def is_json(test_data):
    """
    Converts JSON to dictionary if valid data, otherwise return None.
    """
    try:
        test_json = ujson.loads(test_data.decode('utf-8'))
        return test_json, None
    except Exception as e:
        return None, f"Invalid data received: {e}"

def encode_b64(string):
    """
    Encode string with base64
    """
    return binascii.b2a_base64(string)

def decode_b64(string):
    """
    Decode base64 encoded string
    """
    return binascii.a2b_base64(string)

def xor_encrypt_decrypt(string, key):
    """
    XOR Encrypt string with key
    """
    ## convert text and key to bytes
    string_bytes = string.encode('utf-8')
    key_bytes = key.encode('utf-8')
    
    ## use a list to store result bytes
    result_bytes = bytearray()

    for i in range(len(string_bytes)):
        ## XOR the current byte with the corresponding key byte
        ## Use the modulo operator to cycle through the key
        xor_result = string_bytes[i] ^ key_bytes[i % len(key_bytes)]
        result_bytes.append(xor_result)
    return result_bytes

def message_pack(string, secret):
    """
    Pack string using XOR with secret value
    """
    packed_string = xor_encrypt_decrypt(string.replace(' ', ''), secret)
    return(packed_string)

def message_unpack(string, secret):
    """
    Unpack XOR encrypted string using secret value
    """
    try:
        unpacked_string = xor_encrypt_decrypt(string.decode('utf-8'), secret)
        return(unpacked_string)
    except Exception as e:
        print("Could not unpack received message: ", e)
        None
    
def coord_precision(coordinate):
    """
    Returns string of coordinate to 6 decimal digits
    """
    return str(f"{coordinate:.6f}")

def simplify_display_coordinate(coordinate):
    if (coordinate is not None) and (abs(int(coordinate)) != 0): return coord_precision(coordinate)
    else: return "N/A"


def gps_tuple_to_decimal(latitude_tuple, longitude_tuple):
    """
    Convert GPS from tuple (DD, MM) to decimal degree
    """
    latitude = latitude_tuple[0] + latitude_tuple[1] / 60
    longitude = longitude_tuple[0] + longitude_tuple[1] / 60
    
    ## Sign is determined by hemisphere ('S' or 'N')
    if latitude_tuple[2] == 'S':
        latitude = -latitude
    if longitude_tuple[2] == 'W':
        longitude = -longitude
        
    return (latitude, longitude)


class TimeConverter:
    """
    A MicroPython class for converting between time tuple, Unix epoch,
    and MicroPython epoch.
    """
    # The time difference in seconds between the Unix epoch (1970)
    # and the common MicroPython epoch (2000).
    UNIX_OFFSET_SECONDS = 946684800
    
    def __init__(self, time_tuple=None, unix_epoch=None, micropython_epoch=None):
        """
        Initializes the TimeConverter object with a time.
        You can provide a time tuple, a Unix epoch, or a MicroPython epoch.
        If no time is provided, it uses the current time.
        """
        if time_tuple:
            self._micropython_epoch = utime.mktime(time_tuple)
        elif unix_epoch is not None:
            self._micropython_epoch = unix_epoch - self.UNIX_OFFSET_SECONDS
        elif micropython_epoch is not None:
            self._micropython_epoch = micropython_epoch
        else:
            # If no time specified, use the current time from the RTC
            self._micropython_epoch = utime.time()

    @property
    def time_tuple(self):
        """Returns the time as a utime tuple (year, month, day, ...)."""
        return utime.localtime(self._micropython_epoch)

    @property
    def micropython_epoch(self):
        """Returns the time as an integer, seconds since 2000-01-01."""
        return self._micropython_epoch

    @property
    def unix_epoch(self):
        """Returns the time as an integer, seconds since 1970-01-01."""
        return self._micropython_epoch + self.UNIX_OFFSET_SECONDS

    @classmethod
    def from_unix_epoch(cls, unix_epoch_seconds):
        """Alternative constructor to create an instance from a Unix epoch."""
        return cls(unix_epoch=unix_epoch_seconds)

    @classmethod
    def from_micropython_epoch(cls, micropython_epoch_seconds):
        """Alternative constructor to create an instance from a MicroPython epoch."""
        return cls(micropython_epoch=micropython_epoch_seconds)

# ### How to use the `TimeConverter` class

# Here is a practical example showing how to use the class.

# ```python
# # Create an instance with a time tuple
# # (2025, 9, 20, 17, 47, 0, 5, 263) -> (year, month, day, hour, minute, second, weekday, yearday)
# custom_time = TimeConverter(time_tuple=(2025, 9, 20, 17, 47, 0, 5, 263))

# print("--- Conversions from time tuple ---")
# print(f"Time tuple: {custom_time.time_tuple}")
# print(f"MicroPython epoch: {custom_time.micropython_epoch}")
# print(f"Unix epoch: {custom_time.unix_epoch}\n")


# # Create an instance from a known MicroPython epoch value
# micropython_ts = 811052820  # Corresponds to 2025-09-20 17:47:00 UTC
# mp_time = TimeConverter.from_micropython_epoch(micropython_ts)

# print("--- Conversions from MicroPython epoch ---")
# print(f"Time tuple: {mp_time.time_tuple}")
# print(f"MicroPython epoch: {mp_time.micropython_epoch}")
# print(f"Unix epoch: {mp_time.unix_epoch}\n")


# # Create an instance from a known Unix epoch value
# unix_ts = 1758417620  # Corresponds to 2025-09-20 17:47:00 UTC
# unix_time = TimeConverter.from_unix_epoch(unix_ts)

# print("--- Conversions from Unix epoch ---")
# print(f"Time tuple: {unix_time.time_tuple}")
# print(f"MicroPython epoch: {unix_time.micropython_epoch}")
# print(f"Unix epoch: {unix_time.unix_epoch}\n")


