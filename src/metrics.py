#!/usr/bin/env python3
"""Prometheus metrics definitions for Docker Health Check Suite."""

from prometheus_client import Gauge, Counter, Histogram

class DockerHealthCheckMetrics:
	def __init__(self):
		"""Initialize Prometheus metrics."""
		# Resource metrics
		self.cpu_usage = Gauge(
			"container_cpu_usage_percent", 
			"Container CPU usage percentage",
			["container_name"]
		)
		
		self.memory_usage = Gauge(
			"container_memory_usage_percent",
			"Container memory usage percentage",
			["container_name"]
		)
		
		self.disk_usage = Gauge(
			"container_disk_usage_percent",
			"Container disk usage percentage",
			["container_name"]
		)
		
		# Status metrics
		self.container_up = Gauge(
			"container_up",
			"Container running status (1 for running, 0 for stopped)",
			["container_name"]
		)
		
		self.restart_count = Counter(
			"container_restart_total",
			"Container restart count",
			["container_name"]
		)
		
		# API metrics
		# Response time uses Histogram for percentile calculations
		self.api_response_time = Histogram(
			"api_response_time_seconds",
			"API endpoint response time in seconds",
			["container_name", "endpoint"],
			buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
		)
		
		# Request count uses Counter
		self.api_request_count = Counter(
			"api_request_total",
			"Total number of API requests",
			["container_name", "endpoint", "status_code"]
		)
		
		# Health status uses Gauge
		self.api_health = Gauge(
			"api_health_status",
			"API endpoint health status (1 for healthy, 0 for unhealthy)",
			["container_name", "endpoint"]
		)
		
		# Last status code uses Gauge
		self.api_last_status_code = Gauge(
			"api_last_status_code",
			"Last HTTP status code received from the API endpoint",
			["container_name", "endpoint"]
		)
		
		# Error metrics
		self.error_count = Counter(
			"container_error_total",
			"Container error count",
			["container_name", "error_type"]
		)
