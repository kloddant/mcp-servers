from typing import Dict, Any
import json5 as json

connections: Dict[str, Any] = {}
queries: Dict[str, Any] = {}
results: Dict[str, Any] = {}
env: Dict[str, Any] = {}

def load_config(config_path: str) -> None:
	"""Loads the JSON config into the shared state."""
	try:
		with open(config_path, 'r') as f:
			data = json.load(f)
			env.clear()
			env.update(data)
	except (IOError, json.JSONDecodeError) as e:
		# Standard: specify specific exceptions and use .format()
		print("Failed to load config: {0}".format(str(e)))
		raise
