import threading
import time
import random
from typing import Optional, Coroutine
import asyncio
from tsafepq import ThreadSafePriorityQueue, GlobalState, Idea

class Process(threading.Thread):
    """
    Represents a processing thread that consumes ideas from an input queue,
    processes them, and optionally adds new ideas to output queues.
    """
    
    def __init__(
        self, 
        name: str, 
        global_state: GlobalState, 
        input_queue: Optional[ThreadSafePriorityQueue], 
        output_queues: list[ThreadSafePriorityQueue], 
        stop_event: threading.Event,
        process: Coroutine,
        params: tuple = ()
    ):
        """
        Initializes the Process.
        
        Args:
            name (str): Name of the process for identification.
            global_state (GlobalState): The shared global state.
            input_queue (ThreadSafePriorityQueue): The queue from which to consume ideas.
            output_queues (list[ThreadSafePriorityQueue]): The queues to which to push processed ideas.
            stop_event (threading.Event): Event to signal the thread to stop.
            process (Coroutine): The coroutine to run for processing ideas.
        """
        super().__init__(name=name)
        self.global_state = global_state
        self.input_queue = input_queue
        self.output_queues = output_queues
        self.stop_event = stop_event
        self.process = process
        self.params = params
        
    def run(self):
        """
        The main loop of the process.
        """
        
        print(f"Process '{self.name}': Started.")
        while not self.stop_event.is_set():
            asyncio.run(self.process(self, *self.params))
            
        print(f"Process '{self.name}': Stopped.")


