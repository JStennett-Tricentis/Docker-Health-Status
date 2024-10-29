# Docker Container Health Check Suite

A Python-based testing suite for monitoring and validating Docker container health metrics. This tool provides automated health checks, resource monitoring, and API validation for Docker containers.

## 🚧 POC Status Notice

This project is currently in Proof of Concept phase. For testing purposes, please start the following basic container for testing purposes:

```bash
docker run -d --name test_container nginx:latest
```

Note: This temporary setup will be replaced with the actual production Docker image in future releases.

## Installation

1. Clone the repository:

```bash
git clone https://github.com/JStennett-Tricentis/Docker-Health-Status
cd Docker-Health-Status
```

1. **Configure Environment**

```bash
cp .env.example .env
```

### macOS Installation

1. First, ensure you have Python installed via Homebrew (**if not already installed**):

```bash
brew install python
```

1. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

1. Upgrade pip in the virtual environment:

```bash
python -m pip install --upgrade pip
```

1. Install required packages:

```bash
python -m pip install docker psutil requests
```

### Linux Installation

1. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

1. Install required packages:

```bash
pip install docker psutil requests
```

### Windows Installation

1. Create and activate a virtual environment:

```bash
python -m venv venv
venv\Scripts\activate
```

1. Install required packages:

```bash
pip install docker psutil requests
```

### Development Installation

For development work, it's recommended to use a virtual environment:

```bash
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
# On macOS/Linux:
# source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install development dependencies
python -m pip install -r requirements-dev.txt  # If you have additional development dependencies
```

### Note on Virtual Environments

Virtual environments are isolated Python environments that help avoid conflicts between different projects and system Python packages. When you're done working with the health check suite, you can deactivate the virtual environment:

```bash
deactivate
```

## Configuration

The health check suite can be configured through custom thresholds and monitoring parameters located in the `.env` file:

```python
...
CPU_PERCENT_THRESHOLD=75.0    # CPU usage warning threshold (%)
MEMORY_PERCENT_THRESHOLD=80.0 # Memory usage warning threshold (%)
DISK_PERCENT_THRESHOLD=90.0   # Disk usage warning threshold (%)
RESPONSE_TIME_THRESHOLD=1.5   # API response time threshold (seconds)
RESTART_COUNT_THRESHOLD=3     # Maximum allowed restart count
...
```

## Development and Testing

### Setting Up a Test Environment

1. Create a test container:

```bash
docker run -d --name test_container nginx:latest
```

1. Start the Grafana and Prometheus docker images.

```bash
docker-compose up -d
```

1. Run the health check suite:

```bash
python docker_healthcheck.py
```

### Components

**Prometheus**: Metrics collection and storage:

- Port: `9090`
- Config: `prometheus/prometheus.yml`
- URL: `http://localhost:9090/`
- Dashboard: `http://localhost:9090/targets?search=`

**Grafana**: Visualization and dashboards

- Port: `3000`
- Config: `grafana/provisioning/dashboards/dashboard.yml`
- URL: `http://localhost:3000/`
- Dashboard: `http://localhost:3000/d/docker_healthcheck/docker-health-check-dashboard`

## Usage

### Basic Usage

```python
from docker_healthcheck import DockerHealthCheck

# Initialize with default thresholds
health_check = DockerHealthCheck("your_container_name")

# Run complete health check
results = health_check.run_health_check()
print(json.dumps(results, indent=2))
```

### Sample Output

```json
{
  "timestamp": "2024-10-29T10:30:15.123456",
  "container_name": "test_container",
  "overall_status": "healthy",
  "checks": {
    "container_running": {
      "status": "healthy"
    },
    "resources": {
      "status": "healthy",
      "metrics": {
        "cpu_percent": 45.2,
        "memory_percent": 60.5,
        "disk_percent": 72.1
      }
    },
    "api_health": {
      "status": "healthy",
      "endpoints": [
        {
          "url": "http://localhost:8080/health",
          "response_time": 0.234,
          "status_code": 200,
          "status": "healthy"
        }
      ]
    },
    "logs": {
      "status": "healthy",
      "errors_found": [],
      "error_count": 0
    },
    "restart_count": {
      "status": "healthy",
      "restart_count": 0
    }
  }
}
```

### Logging

Log levels:

- INFO: Normal operations
- WARNING: Thresholds exceeded
- ERROR: Operation failures
