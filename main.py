from flask import Flask, request, Response, json, session

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "Server is live!"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=81)