import requests, json, os
from typing import Dict, Optional
from pathlib import Path
from mcp.server import MCPServer

# Global configuration object
config: Dict = {}

def load_config(path: str) -> None:
	"""Loads the node configuration from a JSON file. Throws error if load fails."""
	global config
	
	absolute_path = os.path.abspath(path)
	
	if not os.path.exists(absolute_path):
		raise FileNotFoundError("Config file not found at {0}".format(absolute_path))

	with open(absolute_path, 'r') as f:
		config = json.load(f)

# Initialize the Synapse MCP Server
mcp = MCPServer("synapse")


@mcp.tool()
async def synapse__ask(prompt: str, agent_id: str = "self") -> str:
	"""
	Sends a task to a specific node in the inference network to save main context.
	
	Args:
		prompt: The task or question for the node.
		agent_id: The ID of the node to use (e.g., 'self', 'laptop', 'old_desktop'). 
		           Defaults to 'self'.
	"""

	def _call_openai_compatible(url: str, prompt: str, model: str) -> str:
		"""Handles requests for OpenAI-compatible APIs (Default: llama.cpp, Ollama, etc)."""
		response = requests.post(
			"{0}/chat/completions".format(url),
			json={
				"messages": [
					{"role": "user", "content": prompt},
				],
				"model": model,
			},
			timeout=120,
		)
		response.raise_for_status()
		data = response.json()
		return data['choices'][0]['message']['content']

	def _call_anthropic(url: str, prompt: str, model: str, api_key: str) -> str:
		"""Handles requests for the native Anthropic Claude API."""
		headers = {
			"x-api-key": api_key,
			"anthropic-version": "2023-06-01",
			"content-type": "application/json",
		}
		response = requests.post(
			url,
			headers=headers,
			json={
				"model": model,
				"max_tokens": 4096,
				"messages": [
					{"role": "user", "content": prompt},
				],
			},
			timeout=120,
		)
		response.raise_for_status()
		data = response.json()
		return data['content'][0]['text']
	
	agents = config.get("agents", {})
	node_data = agents.get(agent_id)
	
	if not node_data:
		available = ", ".join(agents.keys())
		return "Error: Node ID '{0}' not found in config. Available nodes: [{1}]".format(agent_id, available)
	
	url = node_data.get("endpoint")
	if not url:
		return "Error: Node '{0}' is missing an endpoint in config.".format(agent_id)
	
	# Default to 'openai' (llama.cpp compatible) if no provider is listed
	provider = node_data.get("provider", "openai")
	model = node_data.get("model", "helper")
	
	try:
		if provider == "anthropic":
			api_key = node_data.get("api_key")
			if not api_key:
				return "Error: Node '{0}' is configured as anthropic but is missing an api_key.".format(agent_id)
			return _call_anthropic(url, prompt, model, api_key)
		
		# Default path for llama.cpp and other OpenAI-compatible servers
		return _call_openai_compatible(url, prompt, model)
		
	except requests.exceptions.RequestException as e:
		return "Network error communicating with node '{0}' at {1}: {2}".format(agent_id, url, str(e))
	except (KeyError, IndexError) as e:
		return "Error parsing response from node '{0}': {1}".format(agent_id, str(e))
	except Exception as e:
		return "Unexpected error using node '{0}': {1}".format(agent_id, str(e))


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


@mcp.tool()
def synapse__list_agents() -> str:
	"""
	Lists all available agents configured in the synapse network.
	
	Returns:
		A string listing the agent IDs and their basic configuration.
	"""
	agents = config.get("agents", {})
	
	if not agents:
		return "No agents are currently configured in the synapse network."
	
	lines = ["Available Agents:"]
	for agent_id, data in agents.items():
		provider = data.get("provider", "openai")
		model = data.get("model", "helper")
		endpoint = data.get("endpoint", "Unknown")
		lines.append("- {0}: {1} ({2}) at {3}".format(agent_id, model, provider, endpoint))
	
	return "\n".join(lines)
