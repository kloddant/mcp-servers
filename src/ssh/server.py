import json, os, posixpath, paramiko, asyncio, dill, tempfile
from typing import Dict, Tuple, List, Optional
from mcp.server import MCPServer
from pathlib import Path
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("ssh")
manager: Optional['SessionManager'] = None

class SessionManager:
	def __init__(self, config_path: str):
		self.config_path = config_path
		self.config = self._load_config()
		self.sessions: Dict[str, Tuple[paramiko.SSHClient, paramiko.SFTPClient]] = {}

	def _load_config(self):
		with open(self.config_path, 'r') as f:
			return json.load(f)

	@staticmethod
	def init(config_path: str) -> SessionManager:
		return SessionManager(config_path)

	def get_session(self, server_id: str) -> paramiko.SFTPClient:
		if server_id not in self.config['servers']:
			raise ValueError(f"Server {server_id} not found in configuration.")

		if server_id in self.sessions:
			ssh, sftp = self.sessions[server_id]
			try:
				ssh.get_transport().is_active()
				return sftp
			except Exception:
				self.close_session(server_id)

		conf = self.config['servers'][server_id]
		ssh = paramiko.SSHClient()
		ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		ssh.connect(
			conf['host'], 
			username=conf['user'], 
			key_filename=conf['key_path'], 
			passwd=conf.get('key_password'),
		)

		sftp = ssh.open_sftp()
		
		self.sessions[server_id] = (ssh, sftp)
		return sftp

	def close_session(self, server_id: str):
		if server_id in self.sessions:
			ssh, sftp = self.sessions.pop(server_id)
			sftp.close()
			ssh.close()

	def is_path_allowed(self, server_id: str, path: str) -> bool:
		conf = self.config['servers'].get(server_id)
		if not conf: 
			return False
		
		# Clean the requested path
		normalized_path = posixpath.normpath(path)
		allowed_paths = conf.get('allowed_paths', [])
		
		for ap in allowed_paths:
			# Clean the whitelist path
			norm_ap = posixpath.normpath(ap)
			
			# 1. Exact match (it's the folder itself)
			# 2. Child match (it's inside the folder)
			if normalized_path == norm_ap or normalized_path.startswith(norm_ap.rstrip('/') + '/'):
				return True
				
		return False


@mcp.tool()
async def ssh__list_available_servers() -> List[str]:
	"""Returns a list of available SSH servers the LLM can access."""
	return list(manager.config['servers'].keys())


@mcp.tool()
async def ssh__list_remote_files(server_id: str, path: str = "."):
	"""Lists files in a directory on a specific server. Path must be whitelisted."""
	if not manager.is_path_allowed(server_id, path):
		return f"Access Denied: Path {path} is not in the whitelist for {server_id}."
	
	def sync_list():
		sftp = manager.get_session(server_id)
		return "\n".join(sftp.listdir(path))

	try:
		return await asyncio.to_thread(sync_list)
	except Exception as e:
		return f"Error: {str(e)}"


@mcp.tool()
async def ssh__read_remote_file(server_id: str, path: str):
	"""Reads a file from a specific server. Path must be whitelisted."""
	if not manager.is_path_allowed(server_id, path):
		return f"Access Denied: Path {path} is not in the whitelist for {server_id}."
	
	def sync_read():
		sftp = manager.get_session(server_id)
		with sftp.open(path, "r") as f:
			return f.read().decode("utf-8")

	try:
		return await asyncio.to_thread(sync_read)
	except Exception as e:
		return f"Error: {str(e)}"


@mcp.tool()
async def ssh__save_object(id: str) -> str:
	"""
	Saves a stored object to the filesystem to avoid context window limits.
	Returns the absolute path to the saved file.
	"""
	if id not in objects:
		raise ValueError("No object found with ID: {0}".format(id))

	# Get the object from memory
	obj = objects[id]

	# Define the 'jan' directory within the system temp folder
	jan_dir = Path(tempfile.gettempdir()) / "jan"
	
	# Create the directory if it doesn't exist
	jan_dir.mkdir(parents=True, exist_ok=True)

	# Create the final file path
	filename = f"mcp_obj_{id}.pkl"
	file_path = jan_dir / filename

	try:
		# Save the object using dill in binary mode
		with open(file_path, "wb") as f:
			dill.dump(obj, f)
	except Exception as e:
		raise ToolError(f"Failed to serialize object {id}: {str(e)}")

	return str(file_path)


@mcp.tool()
async def ssh__get_documentation() -> str:
	"""
	Purpose: Retrieves the server's documentation, including the state management guide and recommended workflows.
	Produces: The full text of the project readme.
	"""
	try:
		# Resolve the path relative to this script's location
		readme_path = Path(__file__).parent / "readme.md"
		with open(readme_path, "r", encoding="utf-8") as f:
			return f.read()
	except Exception as e:
		return "Documentation currently unavailable: {0}".format(str(e))