import uuid
from mcp.server import MCPServer
from geopy.geocoders import Nominatim
from geopy.distance import geodesic, great_circle
from mcp.server.mcpserver.exceptions import ToolError
from collections.abc import Iterable

mcp = MCPServer("Geography")


objects: dict[str, object] = {}


class Location:

	def __init__(self, *args, **kwargs):

		self.address: str = kwargs.get('address')
		self.latitude: float  = kwargs.get('latitude')
		self.longitude: float = kwargs.get('longitude')
		self.user_agent: str = kwargs.get('user_agent', "geography_mcp_agent")
		self.geolocator: Nominatim = Nominatim(user_agent=self.user_agent)

		if self.address is not None and (self.latitude is None or self.longitude is None):
			self.location = self.geolocator.geocode(self.address)
			self.latitude = self.location.latitude if self.location else None
			self.longitude = self.location.longitude if self.location else None
		if self.latitude is not None and self.longitude is not None and self.address is None:
			self.location = self.geolocator.reverse((self.latitude, self.longitude))
			self.address = self.location.address if self.location else None

		self.coordinates = (self.latitude, self.longitude)

	def distance(self, location_id: str) -> float|None:
		"""
			Purpose: Calculates the distance (in meters) between two locations on the globe.
			Returns: Distance between two locations on the globe, in meters.
		"""
		location = objects.get(location_id)
		if not location:
			return None
		if self.latitude is None or self.longitude is None:
			return None
		if location.latitude is None or location.longitude is None:
			return None
		return geodesic(self.coordinates, location.coordinates).meters


@mcp.tool()
def geography_location(address: str = "", latitude: float = None, longitude: float = None) -> str:
	"""
		Purpose: Create a Location object and return its id.
		Returns: Id of Location object.
	"""
	obj = Location(
		address = address,
		latitude = latitude,
		longitude = longitude,
	)
	obj_id = str(uuid.uuid4())
	objects[obj_id] = obj
	return obj_id


@mcp.tool()
def geography_query(obj_id: str, attr: str, args: list|None = None, kwargs: dict|None = None):
	"""
		Purpose: To execute methods and retrieve property values of Location objects.
		Parameters:
			obj_id: The Location object to execute a method on or to retrieve a property of.
			attr: The Location object method or attribute name.
				Available Location attributes: 'address', 'latitude', 'longitude', 'coordinates'.
				Available Location methods: 'distance'.
			args
			kwargs
				Available kwargs: location_id
		Produces: The Location object method output or attribute value.  If the value is an object or list of objects, it returns the object id(s).  If the value is a distance, it is in meters.
	"""
	args = args or []
	kwargs = kwargs or {}
	obj = objects.get(obj_id)
	if not obj:
		raise ToolError("No existing object found with the id {obj_id}.".format(obj_id = obj_id))
	if not isinstance(obj, Location):
		raise ToolError("obj is not a Location object.")
	if not hasattr(obj, attr):
		available = [a for a in dir(obj) if not a.startswith('__')]
		raise ToolError(f"Object does not implement {attr}. Available attributes/methods are: {', '.join(available)}")

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
def geography_inspect(obj_id: str) -> list:
	"""
		Purpose: List all available attributes and methods for a specific Location object.
	"""
	obj = objects.get(obj_id)
	if not obj:
		raise ToolError(f"No existing object found with the id {obj_id}.")
	return [attr for attr in dir(obj) if not attr.startswith('__')]