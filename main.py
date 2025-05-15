from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "Server is live!"

app.run(host='0.0.0.0', port=81)
