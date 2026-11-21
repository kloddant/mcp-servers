import requests, json, os
from typing import Dict, Optional
from pathlib import Path
from mcp.server import MCPServer

config: Dict = {}
mcp = MCPServer("synapse")


def load_config(path: str) -> None:
	"""Loads the node configuration from a JSON file. Throws error if load fails."""
	global config
	
	absolute_path = os.path.abspath(path)
	
	if not os.path.exists(absolute_path):
		raise FileNotFoundError("Config file not found at {0}".format(absolute_path))

	with open(absolute_path, 'r') as f:
		config = json.load(f)


@mcp.tool()
async def synapse__ask(prompt: str, agent_id: str = "self") -> str:
	"""
	Sends a task to a specific node in the inference network to save main context.
	Args:
		prompt: The task or question for the node.
		agent_id: The ID of the node to use (e.g., 'self', 'laptop', 'old_desktop'). 
		Defaults to 'self'.
	"""
	agents = config.get("agents", {})
	node_data = agents.get(agent_id)
	
	if not node_data:
		available = ", ".join(agents.keys())
		return "Error: Node ID '{0}' not found in config. Available nodes: [{1}]".format(agent_id, available)
	
	url = node_data.get("endpoint")
	if not url:
		return "Error: Node '{0}' is missing an endpoint in config.".format(agent_id)
	
	try:
		# llama.cpp OpenAI-compatible endpoint
		response = requests.post(
			"{0}/chat/completions".format(url),
			json={
				"messages": [
					{"role": "user", "content": prompt},
				],
				"model": "helper",
			},
			timeout=120,
		)
		response.raise_for_status()
	except requests.exceptions.RequestException as e:
		return "Network error communicating with node '{0}' at {1}: {2}".format(agent_id, url, str(e))

	try:
		data = response.json()
		return data['choices'][0]['message']['content']
	except (KeyError, IndexError) as e:
		return "Error parsing response from node '{0}': {1}".format(agent_id, str(e))


@mcp.tool()
def synapse__get_documentation() -> str:
	"""
	Purpose: Retrieves the server's full documentation, including the state management guide and workflows.
	Parameters: None.
	Return value: The full text of the project README.
	"""
	try:
		# Resolve the path relative to this script's location
		readme_path = Path(__file__).parent / "readme.md"
		with open(readme_path, "r", encoding="utf-8") as f:
			return f.read()
	except Exception as e:
		return "Documentation currently unavailable: {0}".format(str(e))