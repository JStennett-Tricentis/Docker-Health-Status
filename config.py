#!/usr/bin/env python3
"""
Configuration handler for Docker Health Check Suite
"""

import os
import json
from dotenv import load_dotenv
from typing import Dict, List, Any

class Config:
	def __init__(self):
		"""Initialize configuration from environment variables."""
		load_dotenv()
		
		# Container configuration
		self.container_name = os.getenv("CONTAINER_NAME", "test_container")
		
		# Resource thresholds
		self.thresholds = {
			"cpu_percent": float(os.getenv("CPU_PERCENT_THRESHOLD", 75.0)),
			"memory_percent": float(os.getenv("MEMORY_PERCENT_THRESHOLD", 80.0)),
			"disk_percent": float(os.getenv("DISK_PERCENT_THRESHOLD", 90.0)),
			"response_time": float(os.getenv("RESPONSE_TIME_THRESHOLD", 1.5)),
			"restart_count": int(os.getenv("RESTART_COUNT_THRESHOLD", 3))
		}
		
		# Logging configuration
		self.log_config = {
			"level": os.getenv("LOG_LEVEL", "INFO"),
			"format": os.getenv("LOG_FORMAT", 
							  "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
			"output_dir": os.getenv("OUTPUT_DIR", "./output"),
			"log_file": os.getenv("LOG_FILE", "docker_healthcheck.log"),
			"retention_days": int(os.getenv("LOG_RETENTION_DAYS", 7))
		}
		
		# API configuration
		self.api_config = {
			"enabled": os.getenv("API_CHECK_ENABLED", "false").lower() == "true",
			"timeout": int(os.getenv("API_TIMEOUT", 5)),
			"retry_attempts": int(os.getenv("API_RETRY_ATTEMPTS", 3))
		}
		
		# Monitoring configuration
		self.monitoring_config = {
			"prometheus_port": int(os.getenv("PROMETHEUS_PORT", 8000)),
			"check_interval": int(os.getenv("CHECK_INTERVAL", 60))
		}
		
		# Error patterns
		self.error_patterns = self._parse_error_patterns()
	
	def _parse_error_patterns(self) -> List[str]:
		"""Parse error patterns from environment variable."""
		patterns = os.getenv("ERROR_PATTERNS", '["ERROR", "FATAL", "Exception"]')
		try:
			return json.loads(patterns)
		except json.JSONDecodeError:
			return ["ERROR", "FATAL", "Exception"]
	
	@property
	def log_file_path(self) -> str:
		"""Get the full path to the log file."""
		return os.path.join(
			self.log_config["output_dir"],
			self.log_config["log_file"]
		)
	
	def to_dict(self) -> Dict[str, Any]:
		"""Convert configuration to dictionary."""
		return {
			"container_name": self.container_name,
			"thresholds": self.thresholds,
			"log_config": self.log_config,
			"api_config": self.api_config,
			"monitoring_config": self.monitoring_config,
			"error_patterns": self.error_patterns
		}
	
	def validate(self) -> None:
		"""Validate configuration values."""
		# Ensure output directory exists
		os.makedirs(self.log_config["output_dir"], exist_ok=True)
		
		# Validate numeric values
		for key, value in self.thresholds.items():
			if not isinstance(value, (int, float)) or value < 0:
				raise ValueError(f"Invalid threshold value for {key}: {value}")
		
		# Validate intervals
		if self.monitoring_config["check_interval"] < 1:
			raise ValueError("Check interval must be positive")
		
		# Validate ports
		if not (1024 <= self.monitoring_config["prometheus_port"] <= 65535):
			raise ValueError("Invalid Prometheus port number")