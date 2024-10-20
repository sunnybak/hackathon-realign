from controller import Controller
from process import Process
from tsafepq import ThreadSafePriorityQueue, GlobalState, Idea
import threading
import curses
import time
import asyncio
from itertools import cycle
from datasets import load_dataset
import random
from typing import Optional

from exa_py import Exa
import json
import aiohttp

import openai

class bcolor:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


client = openai.AsyncOpenAI()

def draw_queue_contents(stdscr, global_state: GlobalState, queue_names: list[str]):
    stdscr.clear()
    height, width = stdscr.getmaxyx()
    
    for i, queue_name in enumerate(queue_names):
        queue: ThreadSafePriorityQueue = global_state.get_queue(queue_name)
        y_pos = i * (height // len(queue_names))
        
        stdscr.addstr(y_pos, 0, f"{queue_name}:", curses.color_pair(i + 1))
        stdscr.addstr(y_pos + 1, 2, f"Size: {queue.size()}", curses.color_pair(i + 1))
        
        items: list[Idea] = queue.peek_all()
        for j, item in enumerate(items[:10]):  # Show up to 10 items
            if y_pos + j + 2 < height:
                stdscr.addstr(y_pos + j + 2, 2, f"{item.abs_rating}/5: {item.seed} (Depth {item.depth})", curses.color_pair(i + 1))

        if queue.size() > 10:
            stdscr.addstr(y_pos + 12, 2, f"... and {queue.size() - 10} more", curses.color_pair(i + 1))
    
    stdscr.refresh()

def visualize_queues(global_state: GlobalState, stop_event: threading.Event):
    def run_visualization(stdscr):
        curses.start_color()
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)

        curses.curs_set(0)  # Hide the cursor
        queue_names = ['seed_queue', 'explore_queue', 'staging_queue']
        
        # Redirect stdout to a file to prevent print statements from interfering
        import sys
        original_stdout = sys.stdout
        sys.stdout = open('output.log', 'w')
        
        try:
            while not stop_event.is_set():
                draw_queue_contents(stdscr, global_state, queue_names)
                time.sleep(0.1)  # Update every 0.1 seconds
        finally:
            # Restore stdout
            sys.stdout.close()
            sys.stdout = original_stdout
    
    curses.wrapper(run_visualization)


class Main:
    
    def __init__(self):
    
        # Load and shuffle the dataset
        persona_hub = load_dataset("proj-persona/PersonaHub", "persona")["train"]
        shuffled_personas = persona_hub.shuffle()
        self.persona_cycle = cycle(shuffled_personas)
        
        # set up the controller with 3 queues: seed_queue, explore_queue, staging_queue
        self.controller: Controller = Controller()
        self.stop_event: threading.Event = self.controller.stop_event
        
        # exa = Exa(api_key="5d59bcdc-cdca-485a-af31-c5e088f048a8")
        
        self.debug = False
        
        # SEED GENERATOR
        async def seed_generator(self, persona_cycle: cycle):
            print(self.name, "started")
            while not self.stop_event.is_set():
                if self.output_queues[0].size() < 10:
                    idea: Idea = Idea(
                        self.global_state,
                        next(persona_cycle)['persona'],
                        depth=0,
                        lineage=[]
                    )
                    self.output_queues[0].push(idea)
                    print(f"{self.name}: Pushed idea {idea.seed} to seed_queue")
                    await asyncio.sleep(0.05)
            print(self.name, "stopped")
        seed_generator_process: Process = Process(
            name='seed_generator',
            global_state=self.controller.global_state,
            input_queue=None,
            output_queues=[self.controller.global_state.get_queue('seed_queue')],
            stop_event=self.stop_event,
            process=seed_generator,
            params=(self.persona_cycle,)
        )
        self.controller.add_process(seed_generator_process)

        # IDEA PUSHER RATER
        async def idea_pusher_rater(self: Process):
            print(self.name, "started")
            BATCH_SIZE = 3
            while not self.stop_event.is_set():
                ideas_to_rate = []
                for _ in range(BATCH_SIZE):
                    idea: Optional[Idea] = self.input_queue.poll()
                    if idea:
                        print(f"{self.name}: Polled idea {idea.seed} from seed_queue")
                        ideas_to_rate.append(idea)
                if ideas_to_rate:
                    rated_ideas = await asyncio.gather(
                        *[self.global_state.rate_absolute(idea) for idea in ideas_to_rate]
                    )
                    for idea, rated_idea in zip(ideas_to_rate, rated_ideas):
                        idea.abs_rating = rated_idea
                        self.output_queues[0].push(idea)
                        print(f"{self.name}: Pushed idea {idea.seed} to explore_queue")
                else:
                    print(f"{self.name}: Seed_queue is empty")
                await asyncio.sleep(0.2)
        
        idea_pusher_rater_process: Process = Process(
            name='idea_pusher_rater',
            global_state=self.controller.global_state,
            input_queue=self.controller.global_state.get_queue('seed_queue'),
            output_queues=[self.controller.global_state.get_queue('explore_queue')],
            stop_event=self.stop_event,
            process=idea_pusher_rater,
            params=()
        )
        self.controller.add_process(idea_pusher_rater_process)
        
        # IDEA EVOLVER
        async def idea_evolver(self: Process):
            print(self.name, "started")
            BATCH_SIZE = 5
            while not self.stop_event.is_set():
                ideas_to_evolve = []
                for _ in range(BATCH_SIZE):
                    idea: Optional[Idea] = self.input_queue.poll()
                    if idea:
                        ideas_to_evolve.append(idea)
                evolved_ideas = await asyncio.gather(
                    *[self.global_state.evolve_idea(idea) for idea in ideas_to_evolve]
                )
                for new_idea in evolved_ideas:
                    if new_idea.depth < 1:
                        self.input_queue.push(new_idea) # push to explore_queue
                    else:
                        self.output_queues[0].push(new_idea) # push to staging_queue
                        print(f"{self.name}: Pushed idea {new_idea.seed} to staging_queue")
                await asyncio.sleep(0.5)
                    
        idea_evolver_process: Process = Process(
            name='idea_evolver',
            global_state=self.controller.global_state,
            input_queue=self.controller.global_state.get_queue('explore_queue'),
            output_queues=[self.controller.global_state.get_queue('staging_queue')],
            stop_event=self.stop_event,
            process=idea_evolver,
            params=()
        )
        self.controller.add_process(idea_evolver_process)
    
    def start(self, runtime_seconds: int):

        # Start the visualization in a separate thread
        if not self.debug:
            self.vis_thread: threading.Thread = threading.Thread(
                target=visualize_queues, 
                args=(self.controller.global_state, self.stop_event),
            )
            
            self.vis_thread.start()

        # Start the Controller
        self.controller.run(runtime_seconds=runtime_seconds)

    def stop(self):
        # After running, print the contents of 'staging_queue' if any remain
        staging_queue: ThreadSafePriorityQueue = self.controller.global_state.get_queue('staging_queue')
        final_ideas = []
        if staging_queue:
            # print("\nFinal Ideas in 'staging_queue':")
            while not staging_queue.is_empty():
                idea = staging_queue.poll()
                if idea:
                    # print(f" - {idea.seed} (Depth: {idea.depth})")
                    self.controller.global_state.messages.append({"role": "assistant", "content": idea.seed})
                    final_ideas.append(idea)
                    
        # Stop the visualization thread
        self.stop_event.set()
        
        return final_ideas



if __name__ == '__main__':
    messages = []
    
    while True:
        main = Main()
        
        user_input = input(f"\n{bcolor.OKCYAN}Enter a prompt (or 'quit' to exit): {bcolor.ENDC}")
        if user_input.lower() == 'quit':
            break
        
        if not main.debug and hasattr(main, 'vis_thread'):
            main.vis_thread.join()
        
        messages.append({"role": "user", "content": user_input})
        main.controller.global_state.messages = messages.copy()
        
        main.start(runtime_seconds=10)
        final_ideas = main.stop()  # Stop the current run before starting a new one
        
        for idea in final_ideas:
            print(f"{bcolor.OKGREEN} - {idea.seed} (Depth: {idea.depth}){bcolor.ENDC}")
        print(f"{bcolor.OKGREEN}--------------------------------{bcolor.ENDC}\n")
        messages.append({"role": "assistant", "content": '\n'.join([idea.seed for idea in final_ideas])})
        main.controller.global_state.messages = messages.copy()
        

    print("Program terminated.")

