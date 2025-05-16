
from flask import Flask, request, Response, json, session
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

@app.route("/", methods=["GET"])
def home():
    return "Server is live!"

if __name__ == "__main__":
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG']
    )
