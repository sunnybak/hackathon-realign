import threading
import bisect
import random
from typing import Any, Callable, Optional
import asyncio
import time
import openai
import json
class GlobalState:
    
    client = openai.AsyncOpenAI(
        base_url="https://api.sambanova.ai/v1",
        api_key="1b8bb659-99f1-4d6c-a5d8-ba40e50abdd5"
    )
    
    def __init__(self):
        self.lock = threading.Lock()
        self.criteria = None
        self.queues = {}
        self.messages = []
        
    def update_criteria(self, new_criteria):
        with self.lock:
            self.criteria = new_criteria
            print(f"GlobalState: Updated criteria to {self.criteria}")
    
    def get_criteria(self):
        with self.lock:
            return self.criteria
    
    def add_queue(self, name: str, queue):
        with self.lock:
            self.queues[name] = queue
            # print(f"GlobalState: Added queue '{name}'")
    
    def get_queue(self, name: str):
        with self.lock:
            return self.queues.get(name, None)

    async def rate_absolute(self, idea: "Idea") -> int:
        prompt = f"Rate the following business idea on a scale of 1-5 for interestingness, viability, and uniqueness. Provide an overall rating that is the average of these three scores. Return your response in strict JSON format. For example, to return a rating of 3.5, return {{'overall_rating': 3.5}}. Business idea: {idea.seed}"

        try:
            overall_rating = random.randint(1, 5)
            
            return int(overall_rating)
        
        except Exception as e:
            print(f"GlobalState: Error rating idea: {e}")
            return 1  # Return the lowest rating if there's an error
    
    async def evolve_idea(self, idea: "Idea") -> "Idea":
        # evolve the idea based on its seed
        prompt = f"Given the persona '{idea.seed}', suggest a unique and innovative consumer AI-powered app tailored to this individual's characteristics and potential interests. Make sure you are basing the ideas based on my previous feedback. Base your response on this conversation. The app idea should be concise, creative, and aligned with the persona's likely preferences and skills. IMPORTANT: Describe the app in one single sentence."
    
        try:
            response = await self.client.chat.completions.create(
                model="Meta-Llama-3.1-8B-Instruct",
                messages=[
                    {"role": "system", "content": "You are a creative business consultant specializing in personalized business ideas. Base your responses on the conversation between the user and assistant."},
                    *self.messages,
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150
            )
            
            new_idea = response.choices[0].message.content.strip()
            
            evolved_idea = Idea(
                global_state=self,
                seed=new_idea,
                depth=idea.depth + 1,
                lineage=idea.lineage + [idea]
            )
            evolved_idea.abs_rating = await self.rate_absolute(evolved_idea)
            
            print(f"GlobalState: Evolved idea '{idea.seed}' into '{evolved_idea.seed}'")
            return evolved_idea
        
        except Exception as e:
            print(f"GlobalState: Error evolving idea: {e}")
            return idea  # Return the original idea if there's an error

class Idea:
    def __init__(
        self, 
        global_state: GlobalState, 
        seed: str, 
        depth: int = 0, 
        lineage: list["Idea"] = []
    ):
        self.global_state = global_state
        self.seed = seed
        self.depth = depth
        self.lineage = lineage.copy()
        
        # Content
        self.content = ''
        
        # Ratings
        self.abs_rating = 0 # absolute rating
        self.elo_rating = 1000 # elo rating
    
    def expand(self) -> list["Idea"]:
        """
        Dummy expand method to simulate idea expansion.
        Generates new ideas with incremented depth.
        """
        if self.depth >= 3:
            # Limit the depth to prevent infinite expansion
            return []
        new_depth = self.depth + 1
        new_lineage = self.lineage + [self]
        expanded_seeds = [f"{self.seed}-{i}" for i in range(2)]  # Expand into two new ideas
        new_ideas = [Idea(self.global_state, seed, new_depth, new_lineage) for seed in expanded_seeds]
        print(f"Idea '{self.seed}' expanded into {[idea.seed for idea in new_ideas]}")
        return new_ideas
    
    def __lt__(self, other: "Idea") -> bool:
        """
        Implements the less than comparison for Idea objects.
        This allows Idea instances to be compared and sorted in priority queues.
        
        Args:
            other (Idea): The other Idea object to compare with.
        
        Returns:
            bool: True if this Idea is considered less than the other, False otherwise.
        """
        # Compare based on depth first (lower depth has higher priority)
        if self.depth != other.depth:
            return self.depth < other.depth
        
        # If depths are equal, compare based on seed length (shorter seed has higher priority)
        return len(self.seed) < len(other.seed)

    def __eq__(self, other: "Idea") -> bool:
        """
        Implements the equality comparison for Idea objects.
        
        Args:
            other (Idea): The other Idea object to compare with.
        
        Returns:
            bool: True if the Ideas are considered equal, False otherwise.
        """
        return self.seed == other.seed and self.depth == other.depth


class ThreadSafePriorityQueue:
    """
    A thread-safe priority queue with a custom heuristic function.
    
    Attributes:
        heuristic_func (Callable[[Any], float]): A function to determine the priority of items.
            Lower values indicate higher priority.
    """
    
    def __init__(
        self, 
        heuristic_func: Optional[Callable[[Any], float]] = None,
        global_state: Optional[GlobalState] = None
    ):
        """
        Initializes the priority queue.
        
        Args:
            heuristic_func (Callable[[Any], float], optional): 
                A function that takes an item and returns its priority.
                If None, a dummy heuristic is used.
            global_state (GlobalState, optional): 
                A shared state object that can be used to store global variables.
        """
        self._lock = threading.Lock()
        self._queue: list[tuple[float, Any]] = []
        self.heuristic_func = heuristic_func if heuristic_func is not None else self.dummy_heuristic
        self.global_state = global_state
        
    def dummy_heuristic(self, item: Any) -> float:
        """
        A dummy heuristic function that assigns a default priority to items.
        Lower priority values are considered higher priority.
        
        Args:
            item (Any): The item to assign a priority.
        
        Returns:
            float: The priority of the item.
        """
        # Example dummy heuristic: priority based on item's string length
        return float(len(str(item)))

    def push(self, item: Any) -> None:
        """
        Pushes an item onto the queue, prioritized based on the heuristic function.
        
        Args:
            item (Any): The item to be added to the queue.
        """
        priority = self.heuristic_func(item)
        with self._lock:
            bisect.insort(self._queue, (priority, item))
            print(f"Pushed item: {item} with priority: {priority}")

    def poll(self) -> Optional[Any]:
        """
        Polls the highest-priority item from the queue.
        
        Returns:
            Optional[Any]: The highest-priority item, or None if the queue is empty.
        """
        with self._lock:
            if not self._queue:
                # print("Poll attempted on empty queue.")
                return None
            priority, item = self._queue.pop(0)
            # print(f"Polled item: {item} with priority: {priority}")
            return item
        
    def poll_many(self, n: int) -> list[Any]:
        """
        Polls multiple items from the queue.
        """
        # with self._lock:
            # if self.size() < n:
            #     n = self.size()
        return [self.poll() for _ in range(n)]

    def poll_random(self) -> Optional[Any]:
        """
        Polls a random item from the queue.
        
        Returns:
            Optional[Any]: A randomly selected item, or None if the queue is empty.
        """
        with self._lock:
            if not self._queue:
                print("Random poll attempted on empty queue.")
                return None
            index = random.randint(0, len(self._queue) - 1)
            priority, item = self._queue.pop(index)
            print(f"Randomly polled item: {item} with priority: {priority}")
            return item

    def peek(self) -> Optional[Any]:
        """
        Peeks at the highest-priority item without removing it.
        
        Returns:
            Optional[Any]: The highest-priority item, or None if the queue is empty.
        """
        with self._lock:
            if not self._queue:
                print("Peek attempted on empty queue.")
                return None
            priority, item = self._queue[0]
            print(f"Peeked at item: {item} with priority: {priority}")
            return item
        
    def peek_all(self) -> list[Any]:
        """
        Peeks at all items in the queue without removing them.
        """
        items = [item for _, item in self._queue]
        items.reverse()
        return items

    def is_empty(self) -> bool:
        """
        Checks if the queue is empty.
        
        Returns:
            bool: True if the queue is empty, False otherwise.
        """
        with self._lock:
            empty = len(self._queue) == 0
            # print(f"Queue is empty: {empty}")
            return empty

    def size(self) -> int:
        """
        Returns the number of items in the queue.
        
        Returns:
            int: The size of the queue.
        """
        with self._lock:
            size = len(self._queue)
            print(f"Queue size: {size}")
            return size

