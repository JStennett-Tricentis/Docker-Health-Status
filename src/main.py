#!/usr/bin/env python3
"""Main entry point for Docker Health Check Suite."""

import signal
import sys
import threading
import time
from datetime import datetime
import os
import json

from src.config import Config
from src.api import start_flask_app
from src.utils import PortManager, print_colored_json
from src.checks import DockerHealthCheck
from prometheus_client import start_http_server

def main():
    """Main function to start health check with Prometheus metrics."""
    port_manager = None
    
    def cleanup_and_exit(signum=None, frame=None):
        """Clean up resources and exit gracefully."""
        print("\n\033[33mReceived shutdown signal. Cleaning up...\033[0m")
        if port_manager:
            port_manager.cleanup()
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, cleanup_and_exit)
    signal.signal(signal.SIGTERM, cleanup_and_exit)
    
    try:
        # Load and validate configuration
        config = Config()
        config.validate()
        
        # Start Flask app in a separate thread
        flask_thread = threading.Thread(target=start_flask_app, daemon=True)
        flask_thread.start()
        print("\033[32mAPI server started on port 5001\033[0m")
        
        # Initialize and start monitoring
        port_manager = PortManager(config.monitoring_config["prometheus_port"])
        prometheus_port = port_manager.find_available_port()
        start_http_server(prometheus_port)
        
        # Initialize health check
        health_check = DockerHealthCheck(config)
        
        # Main monitoring loop
        while True:
            try:
                results = health_check.run_health_check()
                
                if config.log_config["save_output_files"]:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    results_file = os.path.join(
                        config.log_config["output_dir"],
                        f"health_check_{timestamp}.json"
                    )
                    
                    with open(results_file, "w") as f:
                        json.dump(results, f, indent=2)
                    
                    print_colored_json(results)
                    print(f"\n\033[32mResults saved to: {results_file}\033[0m")
                else:
                    print_colored_json(results)
                
                # Wait before next check
                for _ in range(config.monitoring_config["check_interval"]):
                    time.sleep(1)
                    
            except Exception as e:
                print(f"\033[31mError running health check: {str(e)}\033[0m")
                time.sleep(config.monitoring_config["check_interval"])
                
    except Exception as e:
        print(f"\033[31mFatal error: {str(e)}\033[0m")
        cleanup_and_exit()

if __name__ == "__main__":
    main()
