from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
import re,regex, uuid, typeguard, dill, tempfile
from typing import Literal
from collections.abc import Iterable
from pathlib import Path

mcp = MCPServer("Regular Expressions")


objects: dict[str, object] = {}


@mcp.tool()
def regex__compile(pattern: str = "", flags: int = 0) -> str:
	"""
		Purpose: Compile a regular expression pattern into a regular expression object.
		Returns: Id of pattern object.
	"""
	obj = re.compile(pattern=pattern, flags=flags)
	obj_id = str(uuid.uuid4())
	objects[obj_id] = obj
	return obj_id


@mcp.tool()
def regex__query(obj_id: str, attr: str, args: list|None = None, kwargs: dict|None = None):
	"""
		Purpose: To execute methods and retrieve property values of regular expression re.Match and re.Pattern objects.
		Parameters:
			obj_id: The re object to execute a method on or to retrieve a property of.
			attr: The re object method or attribute name.
			args
			kwargs
		Produces: The re object method output or attribute value.  If the value is an object or list of objects, it returns the object id(s).
	"""
	args = args or []
	kwargs = kwargs or {}
	obj = objects.get(obj_id)
	if not obj:
		raise ToolError("No existing object found with the id {obj_id}.".format(obj_id = obj_id))
	if not isinstance(obj, (re.Pattern, re.Match)):
		raise ToolError("obj is not an re.Pattern or re.Match object.")
	if not hasattr(obj, attr):
		raise ToolError("Object does not implement {attr}.".format(attr=attr))

	response = None
	iterable = None
	
	if callable(getattr(obj, attr)):
		try:
			values = getattr(obj, attr)(*args, **kwargs)
		except Exception as e:
			raise ToolError(f"Error calculating {attr}: {str(e)}")
	else:
		values = getattr(obj, attr)

	iterable = isinstance(values, Iterable) and not isinstance(values, (str, bytes))
	if not iterable:
		values = [values]

	response = []
	for value in values:
		if isinstance(value, (str, int, float, bool, type(None))):
			response.append(value)
		else:
			value_id = str(uuid.uuid4())
			response.append(value_id)
			objects[value_id] = value			

	if not iterable:
		response = response[0] if len(response) > 0 else None

	return response


@mcp.tool()
def regex__inspect(obj_id: str) -> list:
	"""
		Purpose: List all available attributes and methods for a specific Regex object.
	"""
	obj = objects.get(obj_id)
	if not obj:
		raise ToolError(f"No existing object found with the id {obj_id}.")
	return [attr for attr in dir(obj) if not attr.startswith('__')]


@mcp.tool()
async def regex__save_object(id: str) -> str:
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
async def regex__get_documentation() -> str:
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