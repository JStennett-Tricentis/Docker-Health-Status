#!/usr/bin/env python3
"""API server for Docker Health Check Suite."""

from flask import Flask, jsonify
from datetime import datetime
from .config import Config

app = Flask(__name__)
config = Config()

@app.route("/health")
def health_check():
	"""Basic health check endpoint."""
	return jsonify({
		"status": "healthy",
		"timestamp": datetime.now().isoformat()
	}), 200

def start_flask_app():
	"""Start Flask app in a separate thread."""
	app.run(
		host=config.api_config["host"],
		port=config.api_config["port"]
	)
