# tracking.py

from utime import ticks_ms
import ujson

rover_file = '/rovers.json'

def load_rovers():
    """
    Load previously stored tracked rovers from file
    """

    try:
        with open(rover_file, 'r') as f:
            rovers_data = ujson.load(f)
        
        for data in rovers_data:
            new_rover = Rover(tracked_data={'id': data['id'],
                                                'lat': data['gps_data']['lat'],
                                                'lon': data['gps_data']['lon'],
                                                'ut': data['gps_data']['ut']},
                                                last_rssi=data['last_rssi'],
                                                last_toa=data['last_toa'])
            
            print("Loaded rover ", new_rover.id, sep='')
    except (OSError, ValueError) as e:
        print("No existing rovers file found or invalid JSON data in ", rover_file, sep='')
        print()
    except Exception as e:
        print("Error loading rovers: ", e, sep='')
        print()


def save_rovers():
    """
    Store known tracked rovers to file
    """

    try:
        rovers_list = [rover.to_dict() for rover in Rover._rovers.values()]
        with open(rover_file, 'w') as f:
            ujson.dump(rovers_list, f)
        print("Trackers saved to ", rover_file, "\n", sep='')
    except Exception as e:
        print("Error saving rovers: ", e, "\n", sep='')


class Rover:
    ## store rover instances
    _rovers = {}
    current_rover_index = 0

    __slots__ = ['id', 'gps_data', 'last_rssi', 'last_track', 'last_toa']
    
    def __init__(self, tracked_data, last_rssi, last_toa):
        """
        Class for storing information on tracked devices
        """
        self.gps_data = {}
        for key in tracked_data:
            if key == 'id':
                self.id = tracked_data.get(key, 'UNKNOWN')
            else:
                self.gps_data[key] = tracked_data.get(key)
        
        self.last_rssi = last_rssi
        self.last_track = ticks_ms()
        self.last_toa = last_toa
        
        self._rovers[self.id] = self
    
    @classmethod
    def get_rover(cls, rover_id):
        """
        Return rover object or None
        """
        return cls._rovers.get(rover_id)

    @classmethod
    def untrack_rover(cls, rover_id):
        result = cls._rovers.pop(rover_id, None)
        
        if result is not None:
            print("Removed ", rover_id, " from tracked rovers", sep='')
        else:
            print("Failed to remove ", rover_id, " from tracked rovers", sep='')


    def update(self, new_rover_data, last_rssi, last_toa):
        for key in new_rover_data:
            if key != 'id':
                self.gps_data[key] = new_rover_data[key]
        
        self.last_rssi = last_rssi
        self.last_track = ticks_ms()
        self.last_toa = last_toa

    def to_dict(self):
        """
        Return rover object as dict
        """
        return {
            'id': self.id,
            'gps_data': self.gps_data,
            'last_rssi': self.last_rssi,
            'last_track': self.last_track,
            'last_toa': self.last_toa
        }


    def list_rovers():
        """
        List known rovers
        """
        return list(Rover._rovers.keys())

