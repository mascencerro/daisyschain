# event.py

import uasyncio as asyncio
from device import Device

# Get the Type objects for coroutines using a temporary function
async def _coro_type_check(): 
    yield
GENERATOR_TYPE = type(_coro_type_check)
COROUTINE_TYPE = type(_coro_type_check())
del _coro_type_check


_TAG = "EventBus"

class EventBus:
    """
    EventBus class
    """
    def __init__(self, device_instance: Device):
        self._device = device_instance
        self.subscribers = {}
        self.active_tasks = set()


    def _log(self, *args):
        if self._device.debug_v:
            self._device.log(_TAG + ": ", *args)


    async def task_cleaner(self):
        """
        Periodically cleans up completed tasks
        """
        self._log("Task cleaner started.")
        
        while True:
            before = len(self.active_tasks)
            self.clean_tasks()
            after = len(self.active_tasks)
            self._log("Task cleaner complete. Results: ", (before - after), " tasks removed, ", after,  " remain")
            
            await asyncio.sleep(15)
            
            
    def clean_tasks(self):
        """
        Removes completed tasks from the active_tasks set
        """
        self.active_tasks = {
            task for task in self.active_tasks if not task.done()
        }
        
        
    def subscribe(self, event_name, handler):
        """
        Adds a handler (sync or async function) to an event
        """
        if event_name not in self.subscribers:
            self.subscribers[event_name] = []
        self.subscribers[event_name].append(handler)
        
    
    def unsubscribe(self, event_name, handler):
        """
        Remove a handler from an event
        """
        if event_name in self.subscribers:
            try:
                self.subscribers[event_name].remove(handler)
                if not self.subscribers[event_name]:
                    del self.subscribers[event_name]
                
                self._log("Unsubscribed handler from '", event_name, "'")
                return True
            
            except ValueError:
                self._log("Handler not found for event '", event_name, "'")
                return False
        else:
            self._log("Event '", event_name, "' not found")

    
    async def emit(self, event_name, *args, **kwargs):
        """
        Emits an event, calling all subscribed handlers
        """
        
        self._log("Bus emit for event: ", event_name, " received")

        if event_name in self.subscribers:
            for handler in self.subscribers[event_name]:
                try:
                    ## Execute the handler/lambda. It returns either None (sync) or a coroutine object.
                    result = handler(*args, **kwargs)
                    
                    ## Check if the result is a coroutine object (as created by async def or lambda calling it)
                    if isinstance(result, COROUTINE_TYPE):
                        ## Schedule the coroutine object as a task ("fire-and-forget")
                        task = asyncio.create_task(result)
                        self.active_tasks.add(task) # Prevents task object from being GC'd immediately
                        
                        ## NOTE: Memory leak issue (task remaining in set after completion)
                        ## is a known limitation of uasyncio without add_done_callback.
                        
                except Exception as e:
                    ## Print full traceback
                    if self._device.debug_v:
                        import sys
                        sys.print_exception(e, sys.stderr)
                    self._log("Error in handler for '", event_name, "': ", e)
                    
            await asyncio.sleep(0)

