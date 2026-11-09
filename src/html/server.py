from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
import uuid, bs4, typeguard, dill, tempfile
from typing import Literal
from collections.abc import Iterable
from pathlib import Path


mcp = MCPServer("Html")


objects: dict[str, object] = {}


@mcp.tool()
def html__parse(html: str = "", parser: Literal["html.parser", "lxml", "lxml-xml", "html5lib"] = "html.parser") -> str:
	"""
		Purpose: Parse html strings.
		Produces: Soup id.
	"""
	soup = bs4.BeautifulSoup(html, parser)
	soup_id = str(uuid.uuid4())
	objects[soup_id] = soup
	return soup_id


@mcp.tool()
def html__query(obj_id: str, attr: str, args: list|None = None, kwargs: dict|None = None):
	"""
		Purpose: To execute methods and retrieve property values of bs4 objects.
		Parameters:
			obj_id: The bs4 object to execute a method on or to retrieve a property of.
			attr: The bs4 object method or attribute name.
			args
			kwargs
		Produces: The bs4 object method output or attribute value.  If the value is an object or list of objects, it returns the object id(s).
	"""
	args = args or []
	kwargs = kwargs or {}
	obj = objects.get(obj_id)
	if not obj:
		raise ToolError("No existing object found with the id {obj_id}.".format(obj_id = obj_id))
	if not isinstance(obj, bs4.PageElement):
		raise ToolError("obj is not a bs4.PageElement.")
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

	iterable = isinstance(values, Iterable) and not isinstance(values, (str, bytes, bs4.PageElement))
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
def html__inspect(obj_id: str) -> list:
	"""
		Purpose: List all available attributes and methods for a specific Html object.
	"""
	obj = objects.get(obj_id)
	if not obj:
		raise ToolError(f"No existing object found with the id {obj_id}.")
	return [attr for attr in dir(obj) if not attr.startswith('__')]


@mcp.tool()
async def html__save_object(id: str) -> str:
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
async def html__get_documentation() -> str:
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