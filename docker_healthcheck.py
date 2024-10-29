#!/usr/bin/env python3
"""
Docker Container Health Check Suite
A comprehensive testing suite for Docker container health monitoring.
"""

import docker
import psutil
import requests
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class DockerHealthCheck:
    def __init__(self, container_name: str, thresholds: Dict = None):
        """
        Initialize health check suite with container name and custom thresholds.
        
        Args:
            container_name: Name or ID of the container to monitor
            thresholds: Dictionary of threshold values for different metrics
        """
        self.container_name = container_name
        self.client = docker.from_env()
        self.logger = self._setup_logging()
        
        # Default thresholds
        self.thresholds = {
            "cpu_percent": 80.0,    # CPU usage threshold (%)
            "memory_percent": 85.0, # Memory usage threshold (%)
            "disk_percent": 90.0,   # Disk usage threshold (%)
            "response_time": 2.0,   # API response time threshold (seconds)
            "restart_count": 3,     # Maximum number of restarts
        }
        
        if thresholds:
            self.thresholds.update(thresholds)

    def _setup_logging(self) -> logging.Logger:
        """Configure logging for the health check suite."""
        logger = logging.getLogger("docker_healthcheck")
        logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File handler
        fh = logging.FileHandler("docker_healthcheck.log")
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
        """
        Check container resource usage (CPU, memory, disk).
        Returns dict with usage metrics and status.
        """
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
            
            # Check if any metrics exceed thresholds
            if cpu_percent > self.thresholds["cpu_percent"]:
                results["status"] = "warning"
                self.logger.warning(f"CPU usage ({cpu_percent}%) exceeds threshold")
            
            if memory_percent > self.thresholds["memory_percent"]:
                results["status"] = "warning"
                self.logger.warning(f"Memory usage ({memory_percent}%) exceeds threshold")
            
            if disk_percent > self.thresholds["disk_percent"]:
                results["status"] = "warning"
                self.logger.warning(f"Disk usage ({disk_percent}%) exceeds threshold")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error checking resource usage: {str(e)}")
            return {"status": "error", "message": str(e)}

    def check_api_health(self, endpoints: List[Dict[str, str]]) -> Dict:
        """
        Check health of API endpoints.
        
        Args:
            endpoints: List of dicts with endpoint details
                      [{"url": "http://...", "method": "GET", "expected_status": 200}]
        """
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
                    timeout=self.thresholds["response_time"]
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
                
                if response_time > self.thresholds["response_time"]:
                    endpoint_status["status"] = "slow"
                    results["status"] = "warning"
                
                results["endpoints"].append(endpoint_status)
                
            except requests.exceptions.RequestException as e:
                results["status"] = "error"
                results["endpoints"].append({
                    "url": endpoint["url"],
                    "status": "error",
                    "error": str(e)
                })
                
        return results

    def check_logs_for_errors(self, error_patterns: List[str]) -> Dict:
        """
        Check container logs for error patterns.
        
        Args:
            error_patterns: List of error strings to search for in logs
        """
        container = self.get_container()
        if not container:
            return {"status": "error", "message": "Container not found"}
            
        try:
            logs = container.logs(tail=1000).decode("utf-8")
            found_errors = []
            
            for pattern in error_patterns:
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
                "status": "warning" if restart_count > self.thresholds["restart_count"] else "healthy",
                "restart_count": restart_count
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def run_health_check(self, endpoints: List[Dict[str, str]] = None, 
                        error_patterns: List[str] = None) -> Dict:
        """
        Run all health checks and return comprehensive results.
        
        Args:
            endpoints: Optional list of API endpoints to check
            error_patterns: Optional list of error patterns to search in logs
        """
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
        
        # Check API endpoints if provided
        if endpoints:
            api_status = self.check_api_health(endpoints)
            health_status["checks"]["api_health"] = api_status
        
        # Check logs for errors if patterns provided
        if error_patterns:
            log_status = self.check_logs_for_errors(error_patterns)
            health_status["checks"]["logs"] = log_status
        
        # Check restart count
        restart_status = self.check_restart_count()
        health_status["checks"]["restart_count"] = restart_status
        
        # Determine overall status
        for check in health_status["checks"].values():
            if check["status"] == "error":
                health_status["overall_status"] = "error"
                break
            elif check["status"] == "warning":
                health_status["overall_status"] = "warning"
        
        return health_status

def main():
    """Main function to demonstrate usage."""
    # Example configuration
    container_name = "test_container"
    custom_thresholds = {
        "cpu_percent": 75.0,
        "memory_percent": 80.0,
        "response_time": 1.5
    }
    
    # Example API endpoints to check
    endpoints = [
        {"url": "http://localhost:8080/health", "method": "GET", "expected_status": 200},
        {"url": "http://localhost:8080/metrics", "method": "GET", "expected_status": 200}
    ]
    
    # Example error patterns to look for in logs
    error_patterns = [
        "ERROR",
        "FATAL",
        "Exception",
        "Failed to connect"
    ]
    
    # Initialize health check
    health_check = DockerHealthCheck(container_name, custom_thresholds)
    
    # Run health check
    results = health_check.run_health_check(endpoints, error_patterns)
    
    # Print results
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
