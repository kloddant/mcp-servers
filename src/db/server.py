import uuid, json5 as json, argparse, re, pathlib
from typing import Dict, List, Any, Optional, Literal
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from connection import Connection
from query import Query, ALLOWED_COMMANDS
from result import Result
from state import connections, queries, results, env

mcp: MCPServer = MCPServer("db")


@mcp.tool()
def db__query(connection_id: str = "", sql: str = "") -> str:
	"""
	Purpose: Executes a read-only SQL query against a specified database connection.
	Parameters:
		- connection_id: The UUID handle of the active connection.
		- sql: The SQL query string to execute.
	Return value: A UUID handle (result_id) for the resulting data set.
	"""
	connection = connections.get(connection_id)
	if not connection:
		raise Exception("Connection does not exist.")
	query = Query.create(connection=connection, sql=sql)
	result = query.execute()
	return result.id


@mcp.tool()
def db__connect_test(connection_name: str = "", database: str = "") -> str:
	"""
	Purpose: Establishes a connection to a database using a predefined connection profile.
	Parameters: 
		- connection_name: The name of the connection profile in the configuration.
		- database: The name of the specific database to use.
	Return value: A UUID handle (connection_id) for the active connection, or an error message.
	"""
	connection_details = env.get("connections", {}).get(connection_name)
	if not connection_details:
		return "Error: Connection name '{0}' does not exist.".format(connection_name)
	
	try:
		connection = Connection.create(database=database, **connection_details)
		return connection.id
	except Exception as e:
		# Return the error as a string so the LLM can actually see it
		return "Error connecting to database: {0}".format(str(e))


@mcp.tool()
def db__connect(connection_name: str = "", database: str = "") -> str:
	"""
	Purpose: Establishes a connection to a database using a predefined connection profile.
	Parameters: 
		- connection_name: Required.  The name of the connection profile in the configuration.
		- database: Optional.  The name of the specific database to use.
	Return value: A UUID handle (connection_id) for the active connection.
	"""
	connection_details = env.get("connections", {}).get(connection_name)
	if not connection_details:
		raise Exception("Connection name does not exist.")
	connection = Connection.create(database=database, **connection_details)
	return connection.id


@mcp.tool()
def db__list_connection_names() -> List[str]:
	"""
	Purpose: Lists all available connection profiles defined in the environment configuration.
	Parameters: None.
	Return value: A list of available connection name strings.
	"""
	connections_config = env.get("connections", {})
	return list(connections_config.keys())


@mcp.tool()
def db__list_connections() -> List[str]:
	"""
	Purpose: Lists all currently active and open database connection handles.
	Parameters: None.
	Return value: A list of active connection UUIDs.
	"""
	return list(connections.keys())


@mcp.tool()
def db__list_allowed_commands() -> List[str]:
	"""
	Purpose: Lists the SQL command prefixes permitted by the server's read-only security policy.
	Parameters: None.
	Return value: A list of permitted SQL keywords.
	"""
	return list(ALLOWED_COMMANDS)


@mcp.tool()
def db__disconnect(connection_id: Optional[str] = None) -> str:
	"""
	Purpose: Closes database connections and removes them from memory to free resources.
	Parameters:
		- connection_id: The UUID of the connection to close. If None, all active connections are closed.
	Return value: A confirmation message string.
	"""
	if connection_id:
		# Close a specific connection
		connection = connections.pop(connection_id, None)
		if not connection:
			raise Exception(f"Connection handle {connection_id} not found.")
		
		connection.disconnect()
		return f"Connection {connection_id} closed successfully."
	
	else:
		# Close all active connections
		count = len(connections)
		# We must create a list of keys first because we are modifying the dict during iteration
		all_ids = list(connections.keys())
		
		for cid in all_ids:
			conn = connections.pop(cid)
			conn.disconnect()
			
		return f"Successfully closed and removed {count} active connections."


@mcp.tool()
def db__get_documentation() -> str:
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
def db__inspect_query(obj_id: str) -> List[str]:
	"""
	Purpose: Lists all available attributes and methods for a specific Query object.
	Parameters:
		- obj_id: The UUID handle of the Query object.
	Return value: A list of attribute and method names.
	"""
	obj = queries.get(obj_id)
	if not obj:
		return ["Error: No existing object found with the id {0}.".format(obj_id)]
	return [attr for attr in dir(obj) if not attr.startswith('__')]


@mcp.tool()
def db__inspect_result(obj_id: str) -> List[str]:
	"""
	Purpose: Lists all available attributes and methods for a specific Result object.
	Parameters:
		- obj_id: The UUID handle of the Result object.
	Return value: A list of attribute and method names.
	"""
	obj = results.get(obj_id)
	if not obj:
		return ["Error: No existing object found with the id {0}.".format(obj_id)]
	return [attr for attr in dir(obj) if not attr.startswith('__')]


@mcp.tool()
def db__dump_object(
	object_ids: List[str], 
	object_property: Optional[str] = None, 
	start_row: int = 0, 
	stop_row: int = 100,
) -> List[str]:
	"""
	Purpose: Retrieves properties or data from any stored database object (Query or Result).
	
	Parameters:
		- object_ids: A list of UUID handles to serialize.
		- object_property: Optional. The name of a specific property to return (e.g., 'rows' for data).
		- start_row: The first row to return if fetching rows.
		- stop_row: The last row to return if fetching rows. Defaults to 100. 
		  Warning: Setting this value too high may clog the LLM context window.  Assume you are running on a local machine, so you have limited context space, or check available context before increasing.
		
	Return value: A list of JSON strings containing the requested data.
	"""
	output = []
	for oid in object_ids:
		# Guard clause: Resolve the object from either store
		obj = results.get(oid) or queries.get(oid)
		if not obj:
			output.append(json.dumps({"error": "Object {0} not found.".format(oid)}))
			continue

		if object_property:
			val = getattr(obj, object_property, "Property {0} not found.".format(object_property))
			
			# Handle pagination for specific row requests
			if object_property == 'rows' and isinstance(val, list):
				val = val[start_row:stop_row]
		else:
			# Default behavior: Return the object dict, capping 'rows' to the stop_row limit
			val = obj.__dict__.copy()
			rows = val.get('rows')
			if isinstance(rows, list):
				val['rows'] = rows[start_row:stop_row]
		
		# Always return a JSON string to maintain consistency
		output.append(json.dumps(val, default=str))
		
	return output
