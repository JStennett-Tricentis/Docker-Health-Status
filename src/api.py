#!/usr/bin/env python3
"""API server for Docker Health Check Suite."""

from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route("/health")
def health_check():
	"""Basic health check endpoint."""
	return jsonify({
		"status": "healthy",
		"timestamp": datetime.now().isoformat()
	}), 200

def start_flask_app():
	"""Start Flask app in a separate thread."""
	app.run(host="0.0.0.0", port=5001)
