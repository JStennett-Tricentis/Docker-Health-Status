from setuptools import setup, find_packages

setup(
    name="docker_healthcheck",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "docker>=6.1.3",
        "psutil>=5.9.0",
        "requests>=2.31.0",
        "pygments>=2.17.0",
        "flask>=3.0.0",
        "prometheus-client>=0.19.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "docker-healthcheck=src.main:main",
        ],
    },
)
