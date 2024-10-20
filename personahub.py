from datasets import load_dataset
from flask import Flask, jsonify
from flask_cors import CORS
from itertools import cycle

# Load and shuffle the dataset
persona_hub = load_dataset("proj-persona/PersonaHub", "persona")["train"]
shuffled_personas = persona_hub.shuffle(seed=42)
persona_cycle = cycle(shuffled_personas)

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return "Hello, World!"

@app.route("/next_persona")
def next_persona():
    persona = next(persona_cycle)
    return jsonify(persona)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
