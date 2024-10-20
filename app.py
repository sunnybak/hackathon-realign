from datasets import load_dataset
from flask import Flask, request, render_template, jsonify
from flask_cors import CORS

# Load and shuffle the dataset
persona_hub = load_dataset("proj-persona/PersonaHub", "persona")["train"]
shuffled_personas = persona_hub.shuffle(seed=42)
current_index = 0

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return "Hello, World!"

@app.route("/next_persona")
def next_persona():
    global current_index
    if current_index >= len(shuffled_personas):
        current_index = 0
    persona = shuffled_personas[current_index]
    current_index += 1
    return jsonify(persona)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
