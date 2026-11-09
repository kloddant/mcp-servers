import uuid, json, dill, tempfile, base64, re, os, datetime
from typing import Literal, Dict, Set, Optional, List, Any
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pathlib import Path

mcp = MCPServer("filesystem")

# Global state
objects: Dict[str, Any] = {}
allowed_directories: Set[str] = set()


class Directory:
	parent_id: Optional[str]
	child_ids: List[str]
	file_ids: List[str]
	absolute_path: str

	def __init__(self, absolute_path: str, parent_id: Optional[str] = None):
		if not any(absolute_path.startswith(allowed) for allowed in allowed_directories):
			raise ToolError("Access denied: Path is not in allowed directories.")
		
		self.absolute_path = absolute_path
		self.parent_id = parent_id
		self.child_ids = []
		self.file_ids = []

	def __str__(self) -> str:
		return "Directory(path={0})".format(self.absolute_path)

	def parent(self) -> Optional[Directory]:
		if not self.parent_id:
			return None
		return objects.get(self.parent_id)

	def children(self) -> List[Directory]:
		return [objects[cid] for cid in self.child_ids if isinstance(objects.get(cid), Directory)]

	def files(self) -> List["File"]:
		return [objects[fid] for fid in self.file_ids if isinstance(objects.get(fid), File)]

	def serialize_tree(self) -> str:
		def build_node(node: Directory):
			return {
				"name": Path(node.absolute_path).name,
				"type": "directory",
				"children": [build_node(objects[cid]) for cid in node.child_ids],
			}
		return json.dumps(build_node(self), indent=2)

	@property
	def file_count(self) -> int:
		return len(self.file_ids)

	@property
	def dir_count(self) -> int:
		return len(self.child_ids)

	@property
	def is_empty(self) -> bool:
		return not self.file_ids and not self.child_ids

	def get_manifest(self, relative_path: str = "") -> dict:
		"""
		Recursively maps the entire directory tree.
		Returns a dictionary: { "path/to/file": "uuid-handle" }
		"""
		manifest = {}
		
		# Process sub-directories
		for cid in self.child_ids:
			child = objects.get(cid)
			if not child:
				continue
			name = Path(child.absolute_path).name
			full_path = "{}/{}".format(relative_path, name) if relative_path else name
			manifest[full_path] = cid
			manifest.update(child.get_manifest(full_path))
			
		# Process files
		for fid in self.file_ids:
			file_obj = objects.get(fid)
			if not file_obj:
				continue
			name = file_obj.name
			full_path = "{}/{}".format(relative_path, name) if relative_path else name
			manifest[full_path] = fid
			
		return manifest
		
	def list_flat(self, relative_path: str = "") -> list:
		"""
		Returns a flat list of all descendants with their handles.
		"""
		manifest = self.get_manifest(relative_path)
		return [{"path": path, "handle": handle} for path, handle in manifest.items()]


class File:
	directory_id: Optional[str]
	name: str
	size: Optional[int]
	absolute_path: str
	mimetype: str

	def __init__(self, absolute_path: str, directory_id: Optional[str] = None):
		if not any(absolute_path.startswith(allowed) for allowed in allowed_directories):
			raise ToolError("Access denied: Path is not in allowed directories.")
		
		self.absolute_path = absolute_path
		self.directory_id = directory_id
		self.name = Path(absolute_path).name
		
		try:
			self.size = Path(absolute_path).stat().st_size
		except Exception:
			self.size = None
			
		self.mimetype = "application/octet-stream"

	def __str__(self) -> str:
		return "File(path={0})".format(self.absolute_path)

	def directory(self) -> Optional[Directory]:
		if not self.directory_id:
			return None
		return objects.get(self.directory_id)

	def b64_encode(self) -> str:
		with open(self.absolute_path, "rb") as f:
			return base64.b64encode(f.read()).decode("utf-8")

	@property
	def extension(self) -> str:
		return Path(self.absolute_path).suffix

	@property
	def is_binary(self) -> bool:
		try:
			with open(self.absolute_path, "rb") as f:
				chunk = f.read(1024)
				return b"\0" in chunk
		except Exception:
			return False


class SearchResult:
	query_params: Dict[str, Any]
	matches: List[Dict[str, Any]] # [{"object_id": str, "line_number": int, "snippet": str}]
	timestamp: datetime.datetime

	def __init__(self, query_params: Dict[str, Any], matches: List[Dict[str, Any]]):
		self.query_params = query_params
		self.matches = matches
		self.timestamp = datetime.datetime.now()

	def __str__(self) -> str:
		return "SearchResult(matches={0}, timestamp={1})".format(len(self.matches), self.timestamp)

	@property
	def match_count(self) -> int:
		return len(self.matches)


@mcp.tool()
async def filesystem__read_directory(dirpath: str) -> str:
	"""
	Returns a Directory object handle. Use filesystem__serialize with object_property='get_manifest' or 'list_flat' to retrieve the names of the files and directories within this handle.
	Purpose: Initializes a Directory object for the given path and populates it with child handles.
	Parameters:
		dirpath: The absolute path to the directory to read.
	Produces: A UUID handle to the created Directory object.
	"""
	if not any(dirpath.startswith(allowed) for allowed in allowed_directories):
		raise ToolError("Access denied: Path is not in allowed directories.")
	
	path_obj = Path(dirpath).resolve()
	
	# Generate ID first so children can reference this parent
	obj_id = str(uuid.uuid4())
	dir_obj = Directory(str(path_obj))
	objects[obj_id] = dir_obj
	
	try:
		entries = list(path_obj.iterdir())
	except Exception as e:
		raise ToolError("Error accessing directory: {0}".format(str(e)))
	
	for entry in entries:
		try:
			if entry.is_dir():
				child_id = str(uuid.uuid4())
				objects[child_id] = Directory(str(entry), parent_id=obj_id)
				dir_obj.child_ids.append(child_id)
			else:
				file_id = str(uuid.uuid4())
				objects[file_id] = File(str(entry), directory_id=obj_id)
				dir_obj.file_ids.append(file_id)
		except Exception:
			continue
	
	return obj_id


@mcp.tool()
async def filesystem__read_file(filepath: str) -> str:
	"""
	Purpose: Initializes a File object for the given path.
	Parameters:
		filepath: The absolute path to the file to read.
	Produces: A UUID handle to the created File object.
	"""
	if not any(filepath.startswith(allowed) for allowed in allowed_directories):
		raise ToolError("Access denied: Path is not in allowed directories.")
	
	path_obj = Path(filepath).resolve()
	file_obj = File(str(path_obj), directory_id=None)
	
	obj_id = str(uuid.uuid4())
	objects[obj_id] = file_obj
	return obj_id


@mcp.tool()
async def filesystem__serialize(
	object_ids: List[str], 
	object_property: Optional[str] = None, 
	start_line: int = 0, 
	stop_line: Optional[int] = None,
) -> str:
	"""
	Purpose: Returns the serialized content or a specific property of one or more objects.
	Parameters:
		object_ids: A list of UUID handles to serialize.
		object_property: Optional. The name of a specific property or method to return.  The object_property parameter can be used to access both attributes and methods of the object (e.g., calling get_manifest on a Directory object).
		start_line: Optional. The first line to read for File objects.
		stop_line: Optional. The last line to read for File objects.
	Produces: A string containing the serialized data, separated by delimiters.
	"""
	results = []
	for oid in object_ids:
		obj = objects.get(oid)
		if not obj:
			results.append("Object {0} not found".format(oid))
			continue
		
		if object_property:
			val = getattr(obj, object_property, None)
			if val is None:
				results.append("Property not found")
				continue
			
			# If the property is a method, execute it
			if callable(val):
				try:
					result = val()
					results.append(str(result))
				except Exception as e:
					results.append("Error executing method {0}: {1}".format(object_property, str(e)))
				continue
			
			results.append(str(val))
			continue

		if isinstance(obj, File):
			try:
				chunk = []
				with open(obj.absolute_path, "r", encoding="utf-8", errors="ignore") as f:
					for i, line in enumerate(f):
						if i < start_line:
							continue
						if stop_line is not None and i >= stop_line:
							break
						chunk.append(line)
				results.append("".join(chunk))
			except (OSError, IOError) as e:
				results.append("Error reading file: {0}".format(str(e)))
				continue

		if isinstance(obj, Directory):
			files_list = ", ".join(obj.file_ids) if obj.file_ids else "None"
			dirs_list = ", ".join(obj.child_ids) if obj.child_ids else "None"
			results.append("Directory: {0}\nFiles (handles): {1}\nDirs (handles): {2}".format(
				obj.absolute_path, 
				files_list, 
				dirs_list,
			))
			continue

		if isinstance(obj, SearchResult):
			if not obj.matches:
				results.append("Search Results: No matches found.")
				continue

			match_strings = []
			for m in obj.matches:
				match_strings.append("Handle: {0} | Line: {1} | Snippet: {2}".format(
					m["object_id"], 
					m["line_number"], 
					m["snippet"],
				))
			results.append("Search Results ({0} matches):\n{1}".format(
				len(obj.matches), 
				"\n".join(match_strings),
			))
			continue

		results.append(str(obj))
	
	return "\n---\n".join(results)


@mcp.tool()
async def filesystem__search(
	dirpath_or_handle: str, 
	pattern: str, 
	types: List[Literal["directories", "files"]], 
	names: bool, 
	contents: bool,
	included_extensions: List[str] = [], 
	excluded_extensions: List[str] = [],
	included_folder_names: List[str] = [],
	excluded_folder_names: List[str] = [],
	max_depth: int = 10,
) -> str:
	"""
	Purpose: Performs a high-precision search for files and directories.
	Parameters:
		dirpath_or_handle: The absolute path OR a UUID handle of a Directory object to search within.
		pattern: The regex pattern to match.
		types: Whether to search for directories, files, or both.
		names: Whether to search directory/file names.
		contents: Whether to search within file contents.  When contents==True, the tool returns a single File handle for each file that contains matches, regardless of how many lines match. The line_number in the SearchResult indicates the specific location of the match within that file."
		included_extensions: Optional. List of extensions to include (e.g., ['.txt', '.py']).
		excluded_extensions: Optional. List of extensions to exclude.
		included_folder_names: Optional. List of folder names to include.
		excluded_folder_names: Optional. List of folder names to exclude.
		max_depth: The maximum directory depth to recurse.
	Produces: A UUID handle to a SearchResult object.
	"""
	# Resolve path from handle if provided
	if dirpath_or_handle in objects:
		obj = objects[dirpath_or_handle]
		if not isinstance(obj, Directory):
			raise ToolError("Handle {0} does not point to a Directory object.".format(dirpath_or_handle))
		dirpath = obj.absolute_path
	else:
		dirpath = dirpath_or_handle

	if not any(dirpath.startswith(allowed) for allowed in allowed_directories):
		raise ToolError("Access denied: Path {0} is not within any allowed directories.".format(dirpath))
	
	regex = re.compile(pattern)
	matches = []
	root_path = Path(dirpath).resolve()
	
	for root, dirs, files in os.walk(root_path):
		depth = root[len(str(root_path)):].count(os.sep)
		if depth > max_depth:
			dirs[:] = []
			continue
		
		if excluded_folder_names:
			dirs[:] = [d for d in dirs if d not in excluded_folder_names]
		
		current_dirs = dirs
		if included_folder_names:
			current_dirs = [d for d in dirs if d in included_folder_names]
		
		if "directories" in types and names:
			for d in current_dirs:
				if regex.search(d):
					full_path = str(Path(root) / d)
					oid = str(uuid.uuid4())
					objects[oid] = Directory(full_path)
					matches.append({"object_id": oid, "line_number": 0, "snippet": d})
		
		if "files" in types:
			for f in files:
				ext = Path(f).suffix
				if included_extensions and ext not in included_extensions:
					continue
				if ext in excluded_extensions:
					continue
				
				full_path = str(Path(root) / f)
				file_oid = None
				
				if names and regex.search(f):
					file_oid = str(uuid.uuid4())
					objects[file_oid] = File(full_path, directory_id=None)
					matches.append({"object_id": file_oid, "line_number": 0, "snippet": f})
				
				if contents:
					try:
						with open(full_path, "r", encoding="utf-8", errors="ignore") as file_handle:
							for i, line in enumerate(file_handle, 1):
								if regex.search(line):
									if file_oid is None:
										file_oid = str(uuid.uuid4())
										objects[file_oid] = File(full_path, directory_id=None)
									matches.append({"object_id": file_oid, "line_number": i, "snippet": line.strip()})
					except (OSError, IOError):
						pass
	
	res_obj = SearchResult({"pattern": pattern, "dirpath": dirpath}, matches)
	res_id = str(uuid.uuid4())
	objects[res_id] = res_obj
	return res_id



@mcp.tool()
async def filesystem__get_handle_by_name(parent_handle: str, name: str) -> str:
	"""
	Purpose: Retrieves the handle of a file or directory by its name within a parent directory.
	Parameters:
		parent_handle: The UUID handle of the parent Directory object.
		name: The name of the file or directory to find.
	Produces: A UUID handle to the child object, or an error if not found.
	"""
	parent = objects.get(parent_handle)
	if not isinstance(parent, Directory):
		raise ToolError("Parent handle {0} is not a valid Directory object.".format(parent_handle))
	
	for fid in parent.file_ids:
		file_obj = objects.get(fid)
		if file_obj and file_obj.name == name:
			return fid
			
	for cid in parent.child_ids:
		dir_obj = objects.get(cid)
		if dir_obj and Path(dir_obj.absolute_path).name == name:
			return cid
			
	raise ToolError("No file or directory named '{0}' found in parent {1}.".format(name, parent_handle))


@mcp.tool()
async def filesystem__list_allowed_directories() -> List[str]:
	"""
	Purpose: Lists all directories that the server is allowed to access.
	Produces: A list of absolute paths to allowed root directories.
	"""
	return list(allowed_directories)


@mcp.tool()
async def filesystem__list_handles() -> str:
	"""
	Purpose: Lists all currently active virtual objects (handles) in the server's memory.
	Produces: A formatted string listing handles and their associated object types.
	"""
	if not objects:
		return "No active handles found."
	
	handles = []
	for oid, obj in objects.items():
		type_name = type(obj).__name__
		handles.append("{0} ({1})".format(oid, type_name))
	
	return "\n".join(handles)


@mcp.tool()
def filesystem__inspect(obj_id: str) -> List[str]:
	"""
	Purpose: Lists all available attributes and methods for a specific filesystem object.
	Parameters:
		obj_id: The UUID handle of the object to inspect.
	Produces: A list of attribute and method names.
	"""
	obj = objects.get(obj_id)
	if not obj:
		raise ToolError("No existing object found with the id {0}.".format(obj_id))
	return [attr for attr in dir(obj) if not attr.startswith('__')]


@mcp.tool()
async def filesystem__get_documentation() -> str:
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

