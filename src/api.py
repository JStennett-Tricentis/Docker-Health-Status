#!/usr/bin/env python3
"""API server for Docker Health Check Suite."""

from flask import Flask, jsonify
from datetime import datetime
import random
from .config import Config

app = Flask(__name__)
config = Config()

@app.route("/health")
def health_check():
	"""Health check endpoint that generates random response codes."""
	# Define possible status codes and their weights
	status_options = [
		(200, 0.7),  # 70% chance of success
		(429, 0.1),  # 10% chance of too many requests
		(500, 0.1),  # 10% chance of server error
		(503, 0.1)   # 10% chance of service unavailable
	]

	# Choose status code based on weights
	status_code = random.choices(
		[code for code, _ in status_options],
		weights=[weight for _, weight in status_options]
	)[0]

	# Define response based on status code
	responses = {
		200: {"status": "healthy", "message": "Service is healthy"},
		429: {"status": "warning", "message": "Too many requests"},
		500: {"status": "error", "message": "Internal server error"},
		503: {"status": "error", "message": "Service unavailable"}
	}

	response = responses[status_code]
	response["timestamp"] = datetime.now().isoformat()
	
	return jsonify(response), status_code

def start_flask_app():
	"""Start Flask app in a separate thread."""
	app.run(
		host=config.api_config["host"],
		port=config.api_config["port"]
	)

if __name__ == "__main__":
	print(f"Starting Flask API on {config.api_config['host']}:{config.api_config['port']}")
	app.run(
		host=config.api_config["host"],
		port=config.api_config["port"]
	)
