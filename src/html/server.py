from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
import uuid, bs4, typeguard
from typing import Literal
from collections.abc import Iterable


mcp = MCPServer("Html")


objects: dict[str, object] = {}


@mcp.tool()
def html_parse(html: str = "", parser: Literal["html.parser", "lxml", "lxml-xml", "html5lib"] = "html.parser") -> str:
	"""
		Purpose: Parse html strings.
		Produces: Soup id.
	"""
	soup = bs4.BeautifulSoup(html, parser)
	soup_id = str(uuid.uuid4())
	objects[soup_id] = soup
	return soup_id


@mcp.tool()
def html_query(obj_id: str, attr: str, args: list|None = None, kwargs: dict|None = None):
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
def html_inspect(obj_id: str) -> list:
	"""
		Purpose: List all available attributes and methods for a specific Html object.
	"""
	obj = objects.get(obj_id)
	if not obj:
		raise ToolError(f"No existing object found with the id {obj_id}.")
	return [attr for attr in dir(obj) if not attr.startswith('__')]