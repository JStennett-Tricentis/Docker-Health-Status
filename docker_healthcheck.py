#!/usr/bin/env python3
"""
Docker Container Health Check Suite with Prometheus Metrics Export
"""

import docker
import psutil
import requests
import time
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from prometheus_client import start_http_server, Gauge, Counter
from config import Config
from flask import Flask, jsonify
import threading

# Initialize Flask app
app = Flask(__name__)

@app.route("/health")
def health_check():
	"""Basic health check endpoint."""
	return jsonify({
		"status": "healthy",
		"timestamp": datetime.now().isoformat()
	}), 200

class DockerHealthCheckMetrics:
	def __init__(self):
		"""Initialize Prometheus metrics."""
		# Resource metrics
		self.cpu_usage = Gauge("container_cpu_usage_percent", 
							  "Container CPU usage percentage",
							  ["container_name"])
		
		self.memory_usage = Gauge("container_memory_usage_percent",
								 "Container memory usage percentage",
								 ["container_name"])
		
		self.disk_usage = Gauge("container_disk_usage_percent",
							   "Container disk usage percentage",
							   ["container_name"])
		
		# Status metrics
		self.container_up = Gauge("container_up",
								"Container running status (1 for running, 0 for stopped)",
								["container_name"])
		
		self.restart_count = Counter("container_restart_total",
								   "Container restart count",
								   ["container_name"])
		
		# API health metrics
		self.api_response_time = Gauge("api_response_time_seconds",
									 "API endpoint response time in seconds",
									 ["container_name", "endpoint"])
		
		self.api_health = Gauge("api_health_status",
							   "API endpoint health status (1 for healthy, 0 for unhealthy)",
							   ["container_name", "endpoint"])
		
		# Error metrics
		self.error_count = Counter("container_error_total",
								 "Container error count",
								 ["container_name", "error_type"])

class DockerHealthCheck:
	def __init__(self, config: Config):
		"""
		Initialize health check with configuration.
		
		Args:
			config: Configuration object containing all settings
		"""
		self.config = config
		self.container_name = config.container_name
		self.client = docker.from_env()
		self.logger = self._setup_logging()
		self.metrics = DockerHealthCheckMetrics()

	def _setup_logging(self) -> logging.Logger:
		"""Configure logging for the health check suite."""
		logger = logging.getLogger("docker_healthcheck")
		logger.setLevel(getattr(logging, self.config.log_config["level"]))
		
		formatter = logging.Formatter(self.config.log_config["format"])
		
		# Create output directory if it doesn't exist
		os.makedirs(self.config.log_config["output_dir"], exist_ok=True)
		
		# Console handler
		ch = logging.StreamHandler()
		ch.setFormatter(formatter)
		logger.addHandler(ch)
		
		# File handler
		fh = logging.FileHandler(self.config.log_file_path)
		fh.setFormatter(formatter)
		logger.addHandler(fh)
		
		return logger

	def get_container(self) -> Optional[docker.models.containers.Container]:
		"""Get container object by name."""
		try:
			return self.client.containers.get(self.container_name)
		except docker.errors.NotFound:
			self.logger.error(f"Container {self.container_name} not found")
			return None

	def check_container_running(self) -> bool:
		"""Verify if container is running."""
		container = self.get_container()
		if not container:
			return False
			
		status = container.status
		self.logger.info(f"Container status: {status}")
		return status == "running"

	def check_resource_usage(self) -> Dict:
		"""Check container resource usage (CPU, memory, disk)."""
		container = self.get_container()
		if not container:
			return {"status": "error", "message": "Container not found"}

		try:
			stats = container.stats(stream=False)
			
			# Calculate CPU usage percentage
			cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
					   stats["precpu_stats"]["cpu_usage"]["total_usage"]
			system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
						 stats["precpu_stats"]["system_cpu_usage"]
			cpu_percent = (cpu_delta / system_delta) * 100.0
			
			# Calculate memory usage percentage
			memory_usage = stats["memory_stats"]["usage"]
			memory_limit = stats["memory_stats"]["limit"]
			memory_percent = (memory_usage / memory_limit) * 100.0
			
			# Get disk usage
			disk_stats = psutil.disk_usage("/")
			disk_percent = disk_stats.percent
			
			results = {
				"status": "healthy",
				"metrics": {
					"cpu_percent": round(cpu_percent, 2),
					"memory_percent": round(memory_percent, 2),
					"disk_percent": round(disk_percent, 2)
				}
			}
			
			# Check thresholds from config
			if cpu_percent > self.config.thresholds["cpu_percent"]:
				results["status"] = "warning"
				self.logger.warning(f"CPU usage ({cpu_percent}%) exceeds threshold")
			
			if memory_percent > self.config.thresholds["memory_percent"]:
				results["status"] = "warning"
				self.logger.warning(f"Memory usage ({memory_percent}%) exceeds threshold")
			
			if disk_percent > self.config.thresholds["disk_percent"]:
				results["status"] = "warning"
				self.logger.warning(f"Disk usage ({disk_percent}%) exceeds threshold")
			
			return results
			
		except Exception as e:
			self.logger.error(f"Error checking resource usage: {str(e)}")
			return {"status": "error", "message": str(e)}

	def check_api_health(self, endpoints: List[Dict[str, str]] = None) -> Dict:
		"""Check health of API endpoints."""
		if not self.config.api_config["enabled"]:
			return {"status": "skipped", "message": "API health check disabled"}

		if not endpoints:
			endpoints = [{"url": "http://localhost:5001/health", "method": "GET"}]

		results = {
			"status": "healthy",
			"endpoints": []
		}
		
		for endpoint in endpoints:
			try:
				start_time = time.time()
				response = requests.request(
					method=endpoint.get("method", "GET"),
					url=endpoint["url"],
					timeout=self.config.api_config["timeout"]
				)
				response_time = time.time() - start_time
				
				endpoint_status = {
					"url": endpoint["url"],
					"response_time": round(response_time, 3),
					"status_code": response.status_code,
					"status": "healthy"
				}
				
				if response.status_code != endpoint.get("expected_status", 200):
					endpoint_status["status"] = "unhealthy"
					results["status"] = "warning"
				
				if response_time > self.config.thresholds["response_time"]:
					endpoint_status["status"] = "slow"
					results["status"] = "warning"
				
				results["endpoints"].append(endpoint_status)
				
			except requests.exceptions.RequestException as e:
				results["status"] = "warning"
				results["endpoints"].append({
					"url": endpoint["url"],
					"status": "error",
					"error": str(e)
				})
				
		return results

	def check_logs_for_errors(self) -> Dict:
		"""Check container logs for error patterns."""
		if not self.config.error_patterns:
			return {"status": "skipped", "message": "No error patterns configured"}

		container = self.get_container()
		if not container:
			return {"status": "error", "message": "Container not found"}
			
		try:
			logs = container.logs(tail=1000).decode("utf-8")
			found_errors = []
			
			for pattern in self.config.error_patterns:
				if pattern in logs:
					found_errors.append(pattern)
			
			return {
				"status": "warning" if found_errors else "healthy",
				"errors_found": found_errors,
				"error_count": len(found_errors)
			}
			
		except Exception as e:
			return {"status": "error", "message": str(e)}

	def check_restart_count(self) -> Dict:
		"""Check container restart count."""
		container = self.get_container()
		if not container:
			return {"status": "error", "message": "Container not found"}
			
		try:
			restart_count = container.attrs["RestartCount"]
			return {
				"status": "warning" if restart_count > self.config.thresholds["restart_count"] else "healthy",
				"restart_count": restart_count
			}
		except Exception as e:
			return {"status": "error", "message": str(e)}

	def update_prometheus_metrics(self, results: Dict) -> None:
		"""Update Prometheus metrics based on health check results."""
		# Update container status
		self.metrics.container_up.labels(container_name=self.container_name).set(
			1 if results["checks"]["container_running"]["status"] == "healthy" else 0
		)

		# Update resource metrics
		if "resources" in results["checks"]:
			metrics = results["checks"]["resources"]["metrics"]
			self.metrics.cpu_usage.labels(container_name=self.container_name).set(
				metrics["cpu_percent"]
			)
			self.metrics.memory_usage.labels(container_name=self.container_name).set(
				metrics["memory_percent"]
			)
			self.metrics.disk_usage.labels(container_name=self.container_name).set(
				metrics["disk_percent"]
			)

		# Update API health metrics
		if "api_health" in results["checks"]:
			for endpoint in results["checks"]["api_health"]["endpoints"]:
				labels = {"container_name": self.container_name, "endpoint": endpoint["url"]}
				if "response_time" in endpoint:
					self.metrics.api_response_time.labels(**labels).set(endpoint["response_time"])
				self.metrics.api_health.labels(**labels).set(
					1 if endpoint["status"] == "healthy" else 0
				)

	def run_health_check(self, endpoints: List[Dict[str, str]] = None) -> Dict:
		"""Run health checks and update Prometheus metrics."""
		health_status = {
			"timestamp": datetime.now().isoformat(),
			"container_name": self.container_name,
			"overall_status": "healthy",
			"checks": {}
		}
		
		# Check if container is running
		is_running = self.check_container_running()
		health_status["checks"]["container_running"] = {
			"status": "healthy" if is_running else "error"
		}
		
		if not is_running:
			health_status["overall_status"] = "error"
			return health_status
		
		# Check resource usage
		resource_status = self.check_resource_usage()
		health_status["checks"]["resources"] = resource_status
		
		# Check API endpoints if enabled
		if self.config.api_config["enabled"]:
			api_status = self.check_api_health(endpoints)
			health_status["checks"]["api_health"] = api_status
		
		# Check logs for errors
		log_status = self.check_logs_for_errors()
		health_status["checks"]["logs"] = log_status
		
		# Check restart count
		restart_status = self.check_restart_count()
		health_status["checks"]["restart_count"] = restart_status
		
		# Determine overall status
		for check in health_status["checks"].values():
			if check["status"] == "error":
				health_status["overall_status"] = "error"
				break
			elif check["status"] == "warning" and health_status["overall_status"] != "error":
				health_status["overall_status"] = "warning"
		
		# Update Prometheus metrics
		self.update_prometheus_metrics(health_status)
		
		return health_status

def print_colored_json(data: Dict) -> None:
	"""Print JSON with syntax highlighting."""
	try:
		from pygments import highlight
		from pygments.lexers import JsonLexer
		from pygments.formatters import TerminalFormatter
		
		json_str = json.dumps(data, indent=2)
		colored_json = highlight(json_str, JsonLexer(), TerminalFormatter())
		print(colored_json)
	except ImportError:
		print(json.dumps(data, indent=2))

class PortManager:
	"""Manage port allocation and cleanup."""
	def __init__(self, start_port: int):
		self.start_port = start_port
		self.current_socket = None
		
	def check_port_available(self, port: int) -> bool:
		"""Check if a port is available."""
		import socket
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			sock.bind(("", port))
			sock.close()
			return True
		except OSError:
			sock.close()
			return False
			
	def find_available_port(self, max_attempts: int = 10) -> int:
		"""Find an available port starting from start_port."""
		for port in range(self.start_port, self.start_port + max_attempts):
			if self.check_port_available(port):
				return port
		raise RuntimeError(f"No available ports found in range {self.start_port}-{self.start_port + max_attempts - 1}")
		
	def cleanup(self) -> None:
		"""Clean up any open sockets."""
		if self.current_socket:
			try:
				self.current_socket.close()
			except Exception:
				pass
			self.current_socket = None

def start_flask_app():
	"""Start Flask app in a separate thread."""
	app.run(host="0.0.0.0", port=5001)

def main():
	"""Main function to start health check with Prometheus metrics."""
	import signal
	import sys
	
	port_manager = None
	
	def cleanup_and_exit(signum=None, frame=None):
		"""Clean up resources and exit gracefully."""
		print("\n\033[33mReceived shutdown signal. Cleaning up...\033[0m")
		if port_manager:
			port_manager.cleanup()
		sys.exit(0)
	
	# Register signal handlers
	signal.signal(signal.SIGINT, cleanup_and_exit)   # Handle Ctrl+C
	signal.signal(signal.SIGTERM, cleanup_and_exit)  # Handle termination request
	
	try:
		# Load and validate configuration
		config = Config()
		config.validate()
		
		# Start Flask app in a separate thread
		flask_thread = threading.Thread(target=start_flask_app, daemon=True)
		flask_thread.start()
		print("\033[32mAPI server started on port 5001\033[0m")
		
		# Initialize port manager
		port_manager = PortManager(config.monitoring_config["prometheus_port"])
		
		# Find available port
		try:
			prometheus_port = port_manager.find_available_port()
			print(f"\033[32mUsing Prometheus port: {prometheus_port}\033[0m")
		except RuntimeError as e:
			print(f"\033[31mError: {str(e)}\033[0m")
			cleanup_and_exit()
		
		# Start Prometheus HTTP server
		try:
			start_http_server(prometheus_port)
			print(f"\n\033[32mPrometheus metrics server started on port {prometheus_port}\033[0m")
			print("\033[33mPress Ctrl+C to stop monitoring\033[0m")
		except Exception as e:
			print(f"\033[31mError starting Prometheus server: {str(e)}\033[0m")
			cleanup_and_exit()
		
		# Initialize health check
		health_check = DockerHealthCheck(config)
		
		while True:
			try:
				# Run health check
				results = health_check.run_health_check()
				
				# Save results to file if enabled
				if config.log_config["save_output_files"]:
					timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
					results_file = os.path.join(
						config.log_config["output_dir"],
						f"health_check_{timestamp}.json"
					)
					
					with open(results_file, "w") as f:
						json.dump(results, f, indent=2)
					
					# Print colored results with file save message
					print_colored_json(results)
					print(f"\n\033[32mResults saved to: {results_file}\033[0m")
				else:
					# Just print colored results without file save message
					print_colored_json(results)
				
				# Wait before next check
				for _ in range(config.monitoring_config["check_interval"]):
					time.sleep(1)  # Sleep in 1-second intervals for better interrupt handling
				
			except Exception as e:
				print(f"\033[31mError running health check: {str(e)}\033[0m")
				# Sleep in 1-second intervals for better interrupt handling
				for _ in range(config.monitoring_config["check_interval"]):
					time.sleep(1)
				
	except Exception as e:
		print(f"\033[31mFatal error: {str(e)}\033[0m")
		cleanup_and_exit()

if __name__ == "__main__":
	main()
