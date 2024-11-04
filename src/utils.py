#!/usr/bin/env python3
"""Utility functions for Docker Health Check Suite."""

import json
from typing import Dict
import socket

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
		raise RuntimeError(
			f"No available ports found in range {self.start_port}-"
			f"{self.start_port + max_attempts - 1}"
		)
		
	def cleanup(self) -> None:
		"""Clean up any open sockets."""
		if self.current_socket:
			try:
				self.current_socket.close()
			except Exception:
				pass
			self.current_socket = None
