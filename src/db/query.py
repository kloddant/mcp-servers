import uuid, re
from typing import Dict, List, Any, Optional, Literal
from pymysql.cursors import DictCursor
from state import connections, queries, results, env


ALLOWED_COMMANDS: set = {"SELECT", "SHOW", "DESC", "DESCRIBE", "USE"}

class Query:
	"""
	Purpose: Represents a single SQL operation and its security validation.
	Responsibilities:
		- Normalizing SQL strings to prevent command obfuscation.
		- Enforcing the read-only policy by blocking forbidden keywords and filesystem functions.
		- Executing the validated SQL through an associated Connection object.
	Attributes:
		- id: A unique UUID identifying this specific query operation.
		- sql: The raw SQL string provided for execution.
		- result: A reference to the resulting Result object after execution.
	"""

	id: str = ""
	connection: object = None
	result: object = None

	def __init__(self, *args, **kwargs):
		self.connection = kwargs.get('connection')
		self.sql = kwargs.get('sql')
		self.id = str(uuid.uuid4())
		if not self.is_read_only():
			raise Exception("Forbidden sql.")
		queries[self.id] = self
	
	@classmethod
	def create(cls, *args, **kwargs):
		return cls(*args, **kwargs)

	def execute(self) -> object:
		from result import Result
		if not self.is_read_only():
			raise Exception("Forbidden sql.")
		
		# Use DictCursor to get rows as dictionaries automatically
		cursor = self.connection.connection.cursor(DictCursor)
		cursor.execute(self.sql)
		rows = cursor.fetchall()
		cursor.close()
		
		self.result = Result.create(
			connection = self.connection,
			query = self,
			sql = self.sql,
			rows = rows, # Pass the fetched rows directly to Result
		)
		return self.result


	def is_read_only(self) -> bool:
		"""
		Defense-in-Depth Normalization Pipeline:
		1. Mask string literals to prevent hiding commands in data.
		2. Strip inert comments.
		3. Unwrap executable comments.
		4. Check for forbidden functions (LOAD_FILE, OUTFILE).
		5. Verify allowed command prefix.
		"""
		sql = self.sql
		
		# 1. Mask string literals ('...' and "...")
		# This prevents an attacker from putting "SELECT" inside a string to fool the prefix check
		sql_norm = re.sub(r"'(?:[^'\\\\]|\\\\.)*'", "''", sql)
		sql_norm = re.sub(r'"(?:[^"\\\\]|\\\\.)*"', '""', sql_norm)

		# 2. Remove single-line comments (-- and #)
		sql_norm = re.sub(r'--.*?$', '', sql_norm, flags=re.MULTILINE)
		sql_norm = re.sub(r'#.*?$', '', sql_norm, flags=re.MULTILINE)

		# 3. Remove inert block comments (/* ... */) but keep executable ones (/*! ... */)
		sql_norm = re.sub(r'/\\*(?!!)[\\s\\S]*?\\*/', '', sql_norm)

		# 4. Unwrap executable comments (strip /*! and */)
		sql_norm = re.sub(r'/\\*!\\d*', ' ', sql_norm)
		sql_norm = sql_norm.replace('*/', ' ')
		
		sql_norm = sql_norm.strip().upper()
		
		if not sql_norm:
			return False

		# 5. Block high-risk functions (Filesystem access)
		if re.search(r'\bLOAD_FILE\s*\(', sql_norm) or re.search(r'\bINTO\s+(OUTFILE|DUMPFILE)\b', sql_norm):
			return False

		# 6. Verify allowed command prefix
		first_word = sql_norm.split()[0]
		return first_word in ALLOWED_COMMANDS