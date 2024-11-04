#!/usr/bin/env python3
"""Health check implementations for Docker Health Check Suite."""

import docker
import psutil
import requests
import time
from typing import Dict, List, Optional
from datetime import datetime
import logging
import os

from .config import Config
from src.metrics import DockerHealthCheckMetrics

class DockerHealthCheck:
	def __init__(self, config):
		"""Initialize health check with configuration."""
		self.config = Config()
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
			default_url = f"http://{self.config.api_config['host']}:{self.config.api_config['port']}/health"
			endpoints = [{"url": default_url, "method": "GET"}]

		results = {
			"status": "healthy",
			"endpoints": []
		}
		
		for endpoint in endpoints:
			try:
				url = endpoint["url"]
				# Basic labels used consistently across all metrics
				labels = {
					"container_name": self.container_name,
					"endpoint": url
				}

				# Start timing the request
				start_time = time.time()
				
				# Make the request
				response = requests.request(
					method=endpoint.get("method", "GET"),
					url=url,
					timeout=self.config.api_config["timeout"]
				)
				
				# Calculate response time
				response_time = time.time() - start_time
				
				# Parse response data
				try:
					response_data = response.json()
				except ValueError:
					response_data = {"message": "Non-JSON response"}
				
				# Record response time
				self.metrics.api_response_time.labels(**labels).observe(response_time)
				
				# Record request count with status code
				self.metrics.api_request_count.labels(
					**labels,
					status_code=str(response.status_code)
				).inc()
				
				# Update last status code
				self.metrics.api_last_status_code.labels(**labels).set(response.status_code)
				
				# Prepare endpoint status
				endpoint_status = {
					"url": url,
					"response_time": round(response_time, 3),
					"status_code": response.status_code,
					"message": response_data.get("message", "No message provided"),
					"timestamp": response_data.get("timestamp", datetime.now().isoformat()),
					"status": "healthy"
				}
				
				# Determine health status based on response code
				if response.status_code == 200:
					endpoint_status["status"] = "healthy"
					self.metrics.api_health.labels(**labels).set(1)
				elif response.status_code == 429:
					endpoint_status["status"] = "warning"
					results["status"] = "warning"
					self.metrics.api_health.labels(**labels).set(0)
					self.logger.warning(f"API rate limit reached: {url}")
				else:
					endpoint_status["status"] = "error"
					results["status"] = "error"
					self.metrics.api_health.labels(**labels).set(0)
					self.logger.error(f"API error: {url} returned {response.status_code}")
				
				# Check response time threshold
				if response_time > self.config.thresholds["response_time"]:
					if endpoint_status["status"] == "healthy":
						endpoint_status["status"] = "warning"
					if results["status"] == "healthy":
						results["status"] = "warning"
					self.logger.warning(
						f"Slow API response: {url} ({response_time:.2f}s > "
						f"{self.config.thresholds['response_time']}s threshold)"
					)
				
				results["endpoints"].append(endpoint_status)
				
			except requests.exceptions.RequestException as e:
				self.logger.error(f"API request failed: {endpoint['url']} - {str(e)}")
				
				# Record failed request
				self.metrics.api_request_count.labels(
					container_name=self.container_name,
					endpoint=endpoint["url"],
					status_code="error"
				).inc()
				
				# Set health status to error
				self.metrics.api_health.labels(
					container_name=self.container_name,
					endpoint=endpoint["url"]
				).set(0)
				
				results["status"] = "error"
				results["endpoints"].append({
					"url": endpoint["url"],
					"status": "error",
					"error": str(e),
					"timestamp": datetime.now().isoformat()
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
				labels = {
					"container_name": self.container_name,
					"endpoint": endpoint["url"]
				}
				
				if "response_time" in endpoint:
					self.metrics.api_response_time.labels(**labels).observe(endpoint["response_time"])

				if "status_code" in endpoint:
					self.metrics.api_last_status_code.labels(**labels).set(endpoint["status_code"])

				# Update request count using Counter
				self.metrics.api_request_count.labels(
					**labels,
					status_code=str(endpoint.get("status_code", "error"))
				).inc()

				# Health status
				self.metrics.api_health.labels(**labels).set(
					1 if endpoint["status"] == "healthy" else 0
				)

	def check_rabbitmq_health(self) -> Dict:
		"""Check RabbitMQ health status."""
		try:
			# RabbitMQ Management API endpoint
			url = f"http://{self.config.rabbitmq_config["host"]}:{self.config.rabbitmq_config["port"]}/api/overview"
			response = requests.get(
				url,
				auth=(self.config.rabbitmq_config["username"], self.config.rabbitmq_config["password"]),
				timeout=5
			)
			
			if response.status_code == 200:
				data = response.json()
				
				# Update metrics
				self.metrics.rabbitmq_up.labels(
					container_name="rabbitmq"
				).set(1)
				
				self.metrics.rabbitmq_connection_count.labels(
					container_name="rabbitmq"
				).set(data["object_totals"]["connections"])
				
				# Check queue statistics
				queue_response = requests.get(
					f"http://{self.config.rabbitmq_config["host"]}:{self.config.rabbitmq_config["port"]}/api/queues",
					auth=(self.config.rabbitmq_config["username"], self.config.rabbitmq_config["password"]),
					timeout=5
				)
				
				if queue_response.status_code == 200:
					queues = queue_response.json()
					for queue in queues:
						self.metrics.rabbitmq_queue_messages.labels(
							container_name="rabbitmq",
							queue=queue["name"]
						).set(queue["messages"])
				
				return {
					"status": "healthy",
					"message": "RabbitMQ is running",
					"details": {
						"version": data["rabbitmq_version"],
						"erlang_version": data["erlang_version"],
						"connections": data["object_totals"]["connections"],
						"queues": data["object_totals"]["queues"],
						"exchanges": data["object_totals"]["exchanges"]
					}
				}
			else:
				self.metrics.rabbitmq_up.labels(container_name="rabbitmq").set(0)
				return {
					"status": "error",
					"message": f"RabbitMQ API returned status {response.status_code}."
				}
				
		except requests.exceptions.RequestException as e:
			self.metrics.rabbitmq_up.labels(container_name="rabbitmq").set(0)
			return {
				"status": "error",
				"message": f"Failed to connect to RabbitMQ: {str(e)}"
			}

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
		
		# Check RabbitMQ status
		rabbitmq_status = self.check_rabbitmq_health()
		health_status["checks"]["rabbitmq"] = rabbitmq_status
		if rabbitmq_status["status"] == "error":
			# Only set overall status to error if it's not already in error state
			if health_status["overall_status"] != "error":
				health_status["overall_status"] = "warning"
		
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
