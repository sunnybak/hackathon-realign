from tsafepq import ThreadSafePriorityQueue, GlobalState, Idea
from process import Process
import threading
import time
import asyncio

class Controller:
    """
    Manages the overall workflow by initializing queues, global state, and processes.
    """
    
    def __init__(self):
        self.global_state: GlobalState = GlobalState()
        
        # Initialize ThreadSafePriorityQueues with dummy heuristic or custom heuristics
        self.queues: dict[str, ThreadSafePriorityQueue] = {
            'seed_queue': ThreadSafePriorityQueue(),
            'explore_queue': ThreadSafePriorityQueue(heuristic_func=lambda x: x.abs_rating),
            'staging_queue': ThreadSafePriorityQueue(heuristic_func=lambda x: x.depth * x.abs_rating)
        }
        
        # Add queues to global state
        for name, queue in self.queues.items():
            self.global_state.add_queue(name, queue)
        
        self.processes: list[Process] = []
        self.stop_event: threading.Event = threading.Event()
    
    def add_process(self, process: Process):
        self.processes.append(process)
    
    def start_processes(self):
        """
        Starts all processes by initiating their threads.
        """
        for process in self.processes:
            print(f"\n\nController: Starting process '{process.name}'...")
            process.start()
            print(f"Controller: Started process '{process.name}'.\n\n")
        print(f"Controller: Started {len(self.processes)} processes.")
    
    def stop_processes(self):
        """
        Signals all processes to stop and waits for them to finish.
        """
        self.stop_event.set()
        for process in self.processes:
            process.join()
        print("Controller: All processes have been stopped.")
        # stop the broadcast thread
        # self.broadcast_thread.join()
        
        # After stopping, you can inspect the 'staging_queue'
        # staging_queue = self.global_state.get_queue('staging_queue')
        # if staging_queue:
        #     print("\nFinal Ideas in 'staging_queue':")
        #     while not staging_queue.is_empty():
        #         idea = staging_queue.poll()
        #         if idea:
        #             print(f" - {idea.seed} (Depth: {idea.depth})")
    
    def enqueue_seed_ideas(self, seeds: list[str]):
        """
        Enqueues initial seed ideas into the seed_queue.
        
        Args:
            seeds (List[str]): A list of seed strings to create Idea instances.
        """
        seed_queue = self.global_state.get_queue('seed_queue')
        if seed_queue is None:
            print("Controller: 'seed_queue' does not exist.")
            return
    
        for seed in seeds:
            idea = Idea(self.global_state, seed)
            seed_queue.push(idea)
            print(f"Controller: Enqueued seed Idea '{idea.seed}' to 'seed_queue'.")
            
    def run(self, runtime_seconds: int = 5):
        """
        Runs the controller by starting processes, enqueuing seed ideas, and managing runtime.
        
        Args:
            runtime_seconds (int): Duration to run the controller.
        """
        try:
            self.start_processes()
            
            # start an asyncio event loop
            # Start broadcasting in a separate thread
            # self.broadcast_thread = threading.Thread(target=asyncio.run, args=(self.broadcast_last_idea(sid, sio),))
            # self.broadcast_thread.start()
            
            # # Save the thread reference in the controller
            # self.broadcast_thread = self.broadcast_thread
            
            time.sleep(runtime_seconds)
            
        except KeyboardInterrupt:
            print("Controller: KeyboardInterrupt received.")
        finally:
            self.stop_processes()
            
            
