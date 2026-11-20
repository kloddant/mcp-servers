import MySQLdb, uuid, pymysql
from typing import Dict, List, Any, Optional, Literal
from mcp.server.mcpserver.exceptions import ToolError
from state import connections, queries, results, env

pymysql.install_as_MySQLdb()

class Connection:
	"""
	Purpose: Manages the low-level lifecycle of a database connection.
	Responsibilities:
		- Establishing the raw socket connection to the MariaDB server.
		- Verifying that the database user has restricted, read-only privileges upon connection.
		- Managing the connection state and cleanup.
	Attributes:
		- id: A unique UUID identifying this specific connection handle.
		- connection: The underlying _mysql connection object.
	"""

	id: str = ""
	connection = None
	cursor = None

	def __init__(self, *args, **kwargs):
		self.host = kwargs.get('host')
		self.port = kwargs.get('port', 3306)
		self.database = kwargs.get('database')
		self.username = kwargs.get('username')
		self.password = kwargs.get('password')
		self.connection = self.connect()
		self.verify_permissions()
		self.id = str(uuid.uuid4())
		connections[self.id] = self
	
	@classmethod
	def create(cls, *args, **kwargs):
		return cls(*args, **kwargs)

	def connect(self):
		params = {
			"host": self.host,
			"port": self.port or 3306,
			"user": self.username, 
			"password": self.password, 
		}
		if self.database:
			params["db"] = self.database
		try:
			self.connection = pymysql.connect(**params)
		except Exception as e:
			raise Exception("Database connection failed: {0}".format(str(e)))
		return self.connection

	def disconnect(self):
		"""Closes the underlying MySQL connection socket."""
		if self.connection:
			try:
				self.connection.close()
			except Exception:
				pass

	def verify_permissions(self) -> None:
		"""
		Checks the current user's grants to ensure they are restricted.
		"""
		forbidden_privs = {
			"FILE", "SUPER", "GRANT OPTION", "INSERT", 
			"UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
		}
		
		try:
			with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
				cursor.execute("SHOW GRANTS")
				grants = cursor.fetchall()
		except Exception as e:
			raise Exception("Failed to verify permissions: {0}".format(str(e)))
		
		for row in grants:
			grant_string = str(next(iter(row.values()))).upper()
			for priv in forbidden_privs:
				if " {0} ".format(priv) in " {0} ".format(grant_string) or grant_string.startswith(priv):
					raise Exception("Security Violation: Database user {0} has forbidden privileges: {1}".format(self.username, priv))
