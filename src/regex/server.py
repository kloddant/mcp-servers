from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
import re,regex, uuid, typeguard
from typing import Literal
from collections.abc import Iterable

mcp = MCPServer("Regular Expressions")


objects: dict[str, object] = {}


@mcp.tool()
def regex_compile(pattern: str = "", flags: int = 0) -> str:
	"""
		Purpose: Compile a regular expression pattern into a regular expression object.
		Returns: Id of pattern object.
	"""
	obj = re.compile(pattern=pattern, flags=flags)
	obj_id = str(uuid.uuid4())
	objects[obj_id] = obj
	return obj_id


@mcp.tool()
def regex_query(obj_id: str, attr: str, args: list|None = None, kwargs: dict|None = None):
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
def regex_inspect(obj_id: str) -> list:
	"""
		Purpose: List all available attributes and methods for a specific Regex object.
	"""
	obj = objects.get(obj_id)
	if not obj:
		raise ToolError(f"No existing object found with the id {obj_id}.")
	return [attr for attr in dir(obj) if not attr.startswith('__')]