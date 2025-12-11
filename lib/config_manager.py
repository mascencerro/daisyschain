# config_manager.py

import ujson
import os

board_config = {}
# board = "HeltecWiFiLoRa32v3"
board = "GENERIC"

board_file = "/board.txt"
pref_file = "/config.json"


def load_board_config():
    """
    Load board configuration data
    """
    global board_config
    global board
    
    if not board_file.strip('/') in os.listdir('/'):
        print("Board not specified in /board.txt or file not found, using default:", board)
        print()
    else:
        try:
            with open(board_file, 'r') as f:
                board_dir = f.readline().strip()
                if 'config.py' in os.listdir(f'/lib/board/{board_dir}'):
                    board = board_dir
                    
        except Exception as e:
            print("Could not load configuration specified in ", board_file, ": /lib/board/", board_dir, "/config.py : ", e, sep='')
            print("Falling back to ", board, sep='')
    
    preferences_temp = load_preferences(board)
    board_name = preferences_temp.get('board', board)
    
    try:
        ## dynamically import board specific config
        module_name = f"board.{board_name}.config"
        board_module = __import__(module_name, globals(), locals(), [''], 0)
        
        for key in dir(board_module):
            if not key.startswith('_'):
                board_config[key] = getattr(board_module, key)
        
        print("Board-specific configuration for ", board_name, " loaded", sep='')
        
        ## Clear loaded board module from memory
        import sys
        if module_name in sys.modules:
            del sys.modules[module_name]
        del board_module
        
        return preferences_temp
    except (ImportError, AttributeError) as e:
        print("Error: Unable to load board configuration for '", board_name, "': ", e, sep='')
        return {}



def load_preferences(board):
    """
    Load previously stored device preferences from file
    """
    preferences = {}
    
    try:
        with open(pref_file, 'r') as f:
            preferences = ujson.load(f)
            print("Preferences loaded.")
            
    except ValueError:
        print("Invalid JSON format in '", pref_file, "', recreating with defaults", sep='')
        
    except OSError:
        print("Preferences file '", pref_file, "' not found, creating with defaults", sep='')

    print()
    preferences['board'] = board
    save_preferences(preferences)
    return preferences


def save_preferences(data):
    """
    Store device preferences to file
    """

    try:
        with open(pref_file, 'w') as f:
            ujson.dump(data, f)
            print("Preferences saved.")
            print()
    except Exception as e:
        print("Error saving preferences: ", e, sep='')
        print()


def reset_preferences():
    """
    Reset preferences stored in file (delete file)
    """
    try:
        os.remove(pref_file)
        print("Stored configuration file '", pref_file, "' deleted", sep='')
        print("Device will need to be restarted if it does not do so automatically")
    except Exception as e:
        print("Could not delete configuration file '", pref_file, "': ", e, sep='')
    

def update_preference(preferences, key, value):
    """
    Update single device preference
    """
    keys = key.split('.')
    current_dict = preferences

    ## Traverse the dictionary to the final key
    for k in keys[:-1]:
        # If the key doesn't exist or is not a dictionary, create it
        if k not in current_dict or not isinstance(current_dict[k], dict):
            current_dict[k] = {}
        current_dict = current_dict[k]

    ## Update the final key
    current_dict[keys[-1]] = value
    print("\t#--> '", key, "' = '", value, "'", sep='')


def update_preferences(preferences, new_preferences_dict):
    """
    Update multiple device preferences
    
    For nested dictionary use '.' to denote hierarchy
    """
    for key, value in new_preferences_dict.items():
        if key == 'id' and len(value) > 20:
            value = value[:20]
            print("Device ID longer than 20 characters, using ", value, sep='')
        update_preference(preferences, key, value)
    
    ## Save to file
    print("Storing preferences: \n", preferences, "\n", sep='')
    save_preferences(preferences)


