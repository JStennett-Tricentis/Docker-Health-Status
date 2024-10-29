# Docker Health Check Suite Makefile
# Provides npm-like shortcuts for common Python development tasks

# Install all project dependencies
install:
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt

# Run the main health check application
run:
	python docker_healthcheck.py

# Start the monitoring stack (Prometheus + Grafana)
monitoring-up:
	docker-compose up -d

# Stop the monitoring stack
monitoring-down:
	docker-compose down

# Start a test container for development
test-container:
	docker run -d --name test_container nginx:latest

# Remove test container
clean-test:
	docker rm -f test_container || true

# Format code using black
format:
	pip install black
	black .

# Run code linting
lint:
	pip install pylint
	pylint *.py

# Clean Python cache files
clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete

# Full development setup
setup: install monitoring-up test-container

# Tear down everything
teardown: monitoring-down clean-test clean

.PHONY: install run monitoring-up monitoring-down test-container clean-test format lint clean setup teardown
