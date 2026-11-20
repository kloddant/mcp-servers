import uuid
from typing import Dict, List, Any, Optional, Literal
from state import connections, queries, results, env


class Result:
	"""
	Purpose: Captures and stores the data returned by a Query execution.
	Responsibilities:
		- Retrieving the result set from the database server.
		- Converting raw database rows into a Python-accessible format (dictionaries).
	Note: This class bypasses the standard Python DB-API (Cursor) and directly 
	utilizes the low-level MySQLdb._mysql.store_result and fetch_row mechanisms 
	to manage the result buffer.
	Attributes:
		- id: A unique UUID identifying this specific result set.
		- rows: A list of dictionaries containing the fetched data.
		- sql: The SQL query that produced this result.
	"""

	id: str = ""
	query: object = None
	connection: object = None
	rows: dict = {}

	def __init__(self, *args, **kwargs):
		self.connection = kwargs.get('connection')
		self.query = kwargs.get('query')
		self.sql = kwargs.get('sql')
		self.rows = kwargs.get('rows', []) # Use rows passed from Query.execute
		self.id = str(uuid.uuid4())
		results[self.id] = self

	@classmethod
	def create(cls, *args, **kwargs):
		return cls(*args, **kwargs)