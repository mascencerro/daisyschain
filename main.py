# main.py

import machine
import gc
import uasyncio as asyncio

from device import Device
import config_manager as conf

device_instance = Device(conf.load_board_config())

WD_TIMER = conf.board_config.get('WATCHDOG')


async def watchdog_feeder(wd):
    while True:
        wd.feed()
        await asyncio.sleep_ms(1000)


async def main():
    gc.enable()

    asyncio.create_task(device_instance.bus.task_cleaner())
    asyncio.create_task(device_instance.check_button())

    if device_instance.wd:
        watchdog = machine.WDT(timeout=WD_TIMER)
        asyncio.create_task(watchdog_feeder(watchdog))
        if device_instance.debug_v:
            print("Watchdog timeout set to: ", WD_TIMER, "ms (", (WD_TIMER // 1000), "seconds)", sep='')
    else:
        watchdog = None
        if device_instance.debug_v:
            print("Watchdog disabled.")
    
    try:
        if device_instance.lora is not None:
            asyncio.create_task(device_instance.lora.check_incoming_queue())
        ## Is device Rover or Base?
        if device_instance.is_rover:
            import rover_device
            device = rover_device.RoverDeviceHandler(device_instance)
            del rover_device
        else:
            import base_device
            device = base_device.BaseDeviceHandler(device_instance)
            del base_device
        
        gc.collect()
        # print(gc.mem_free())
        asyncio.create_task(device.run())
        
        while True:
            await asyncio.sleep(60)

    except Exception as e:
        print("FATAL ERROR IN MAIN LOOP! Could not start asyncio task list!")
        print("ERROR: ", e)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("Error in event loop: ", e)

