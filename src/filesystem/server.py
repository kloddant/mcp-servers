import uuid, json, os, datetime, re, glob, mimetypes
from typing import Literal, Dict, Set, Optional, List, Any, Union
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pathlib import Path

mcp = MCPServer("filesystem")

# Global state
objects: Dict[str, Any] = {}
allowed_directories: Set[str] = set()
cwd: str = ""


class Directory:
	absolute_path: str

	def __init__(self, absolute_path: str):
		self.absolute_path = absolute_path
		self._entries: List[Path] = []
		self._populated = False

	def populate(self):
		"""Reads the directory from disk."""
		if self._populated:
			return
		
		try:
			path_obj = Path(self.absolute_path)
			if path_obj.is_dir():
				self._entries = list(path_obj.iterdir())
				self._populated = True
		except (PermissionError, OSError):
			pass

	def get_entries(self) -> List[Path]:
		self.populate()
		return self._entries

	def __str__(self) -> str:
		return "Directory(path={0})".format(self.absolute_path)


class File:
	absolute_path: str
	name: str
	size: Optional[int]

	def __init__(self, absolute_path: str):
		self.absolute_path = absolute_path
		self.name = Path(absolute_path).name
		
		try:
			self.size = Path(absolute_path).stat().st_size
		except Exception:
			self.size = None

	def get_line_count(self) -> int:
		count = 0
		try:
			with open(self.absolute_path, "r", encoding="utf-8", errors="ignore") as f:
				for _ in f:
					count += 1
		except (OSError, IOError):
			return 0
		return count

	def read_lines(self, start: int, stop: Optional[int] = None) -> str:
		lines = []
		try:
			with open(self.absolute_path, "r", encoding="utf-8", errors="ignore") as f:
				for i, line in enumerate(f):
					if i < start:
						continue
					if stop is not None and i >= stop:
						break
					lines.append(line)
		except (OSError, IOError) as e:
			return "Error reading file: {0}".format(str(e))
		return "".join(lines)

	def __str__(self) -> str:
		return "File(path={0})".format(self.absolute_path)


class GrepResult:
	matches: List[Dict[str, Any]] # [{"path": str, "line": int, "snippet": str}]

	def __init__(self, matches: List[Dict[str, Any]]):
		self.matches = matches

	def __str__(self) -> str:
		if not self.matches:
			return "No matches found."
		
		output = ["Grep Results ({0} matches):".format(len(self.matches))]
		for m in self.matches:
			output.append("Path: {0} | Line: {1} | Snippet: {2}".format(
				m["path"],
				m["line"],
				m["snippet"],
			))
		return "\n".join(output)


class FindResult:
	paths: List[str]

	def __init__(self, paths: List[str]):
		self.paths = paths

	def __str__(self) -> str:
		if not self.paths:
			return "No files found matching pattern."
		
		return "Find Results ({0} matches):\n{1}".format(
			len(self.paths),
			"\n".join(self.paths),
		)


def _resolve_and_verify_path(path: Optional[str]) -> str:
	"""
	Resolves a path (relative to CWD if necessary) and verifies 
	it is within the allowed directories.
	"""
	if not path:
		if not cwd:
			raise ToolError("No path provided and CWD is not set.")
		target_path = cwd
	else:
		target_path = path

	# Handle relative paths
	path_obj = Path(target_path)
	if not path_obj.is_absolute():
		if not cwd:
			raise ToolError("Relative path provided but CWD is not set.")
		path_obj = Path(cwd) / path_obj
	
	absolute_path = str(path_obj.resolve())

	if not any(absolute_path.startswith(allowed) for allowed in allowed_directories):
		raise ToolError("Access denied: Path {0} is not in allowed directories.".format(absolute_path))
	
	return absolute_path


def _get_cached_object(path: str, obj_type: type) -> Any:
	"""Retrieves an object from the cache or creates it if missing."""
	if path in objects and isinstance(objects[path], obj_type):
		return objects[path]
	
	if obj_type == Directory:
		obj = Directory(path)
	elif obj_type == File:
		obj = File(path)
	else:
		raise ValueError("Unsupported object type for caching.")
	
	objects[path] = obj
	return obj


@mcp.tool()
async def filesystem__pwd() -> str:
	"""Returns the current working directory."""
	return cwd if cwd else "CWD not set."


@mcp.tool()
async def filesystem__cd(path: str) -> str:
	"""Changes the current working directory."""
	global cwd
	verified_path = _resolve_and_verify_path(path)
	
	if not Path(verified_path).is_dir():
		raise ToolError("Path {0} is not a directory.".format(verified_path))
	
	cwd = verified_path
	return "Changed directory to {0}".format(cwd)


@mcp.tool()
async def filesystem__ls(
	path: Optional[str] = None, 
	start_index: int = 0, 
	stop_index: Optional[int] = 100,
) -> str:
	"""
	Lists the filenames and directory names in a directory.
	Parameters:
		path: The path to list. If omitted, uses CWD.
		start_index: The index of the first entry to return.
		stop_index: The index of the last entry to return. Defaults to 100.
	"""
	verified_path = _resolve_and_verify_path(path)
	dir_obj = _get_cached_object(verified_path, Directory)
	entries = dir_obj.get_entries()
	
	total = len(entries)
	subset = entries[start_index:stop_index] if stop_index is not None else entries[start_index:]
	
	output = ["Directory Listing for {0} (Total: {1})".format(verified_path, total)]
	for entry in subset:
		type_label = "[DIR]" if entry.is_dir() else "[FILE]"
		output.append("{0} {1}".format(type_label, entry.name))
	
	return "\n".join(output)


@mcp.tool()
async def filesystem__tree(
	path: Optional[str] = None, 
	max_depth: int = 0,
	folders_only: bool = False,
) -> str:
	"""
	Lists the contents of a directory in a structured JSON format.
	Parameters:
		path: The path to list. If omitted, uses CWD.
		max_depth: How many levels of subdirectories to recurse into. Default is 0.
		folders_only: If True, only directories are included in the tree.
	"""
	def build_tree(path: Path, current_depth: int) -> Dict[str, Any]:
		"""Internal helper to recursively build the directory tree."""
		node = {
			"name": path.name,
			"type": "directory",
			"path": str(path),
			"children": []
		}
		
		if current_depth < max_depth:
			try:
				for entry in path.iterdir():
					if entry.is_dir():
						node["children"].append(build_tree(entry, current_depth + 1))
					elif not folders_only:
						node["children"].append({
							"name": entry.name,
							"type": "file",
							"path": str(entry),
							"size": entry.stat().st_size
						})
			except (PermissionError, OSError):
				pass
		return node

	verified_path = _resolve_and_verify_path(path)
	root_path = Path(verified_path)
	
	if not root_path.is_dir():
		raise ToolError("Path {0} is not a directory.".format(verified_path))
	
	tree = build_tree(root_path, 0)
	return json.dumps(tree, indent=2)


@mcp.tool()
async def filesystem__cat(
	path: Union[str, List[str]], 
	start_line: int = 0, 
	stop_line: Optional[int] = 100,
) -> str:
	"""
	Reads the contents of one or more files.
	Parameters:
		path: The path to the file, or a list of paths to multiple files.
		start_line: The first line to read. Defaults to 0.
		stop_line: The last line to read. Defaults to 100.
	"""
	paths = [path] if isinstance(path, str) else path
	
	results = []
	for p in paths:
		try:
			verified_path = _resolve_and_verify_path(p)
			file_obj = _get_cached_object(verified_path, File)
			
			total_lines = file_obj.get_line_count()
			content = file_obj.read_lines(start_line, stop_line)
			
			# Determine the actual stop line for the header
			effective_stop = stop_line if stop_line is not None else total_lines
			
			header = "File: {0} (Start Line: {1}, Stop Line: {2}, Total Lines in File: {3})".format(
				verified_path,
				start_line,
				effective_stop,
				total_lines,
			)
			results.append("{0}\n---\n{1}".format(header, content))
			
		except ToolError as e:
			results.append("Error accessing {0}: {1}".format(p, str(e)))
		except Exception as e:
			results.append("Unexpected error reading {0}: {1}".format(p, str(e)))
	
	return "\n\n".join(results)


@mcp.tool()
async def filesystem__stat(path: str) -> str:
	"""Returns comprehensive metadata about a file or directory."""
	verified_path = _resolve_and_verify_path(path)
	path_obj = Path(verified_path)
	
	if not path_obj.exists():
		raise ToolError("Path {0} does not exist.".format(verified_path))
	
	stats = path_obj.stat()
	is_dir = path_obj.is_dir()
	
	# Detect MIME type
	mime_type, _ = mimetypes.guess_type(verified_path)
	if is_dir:
		mime_type = "directory"
	elif mime_type is None:
		mime_type = "application/octet-stream" # Default for unknown binary files
	
	return "Stat for {0}:\nType: {1}\nSize: {2} bytes\nModified: {3}\nCreated: {4}\nPermissions: {5:o}\nUID: {6}\nGID: {7}\nMIME Type: {8}".format(
		verified_path,
		"Directory" if is_dir else "File",
		stats.st_size,
		datetime.datetime.fromtimestamp(stats.st_mtime).isoformat(),
		datetime.datetime.fromtimestamp(stats.st_ctime).isoformat(),
		stats.st_mode,
		stats.st_uid,
		stats.st_gid,
		mime_type,
	)


@mcp.tool()
async def filesystem__glob(
	pattern: str, 
	path: Optional[str] = None,
) -> str:
	"""
	Finds files and directories using glob patterns (e.g., '**/*.py').
	Parameters:
		pattern: The glob pattern to match.
		path: The root directory to start the search. If omitted, uses CWD.
	"""
	verified_path = _resolve_and_verify_path(path)
	root_path = Path(verified_path)
	
	# Use rglob if the pattern starts with ** or contains it, otherwise use glob
	if "**" in pattern:
		matches = list(root_path.rglob(pattern))
	else:
		matches = list(root_path.glob(pattern))
		
	found_paths = [str(p) for p in matches]
	
	return "Glob Results ({0} matches):\n{1}".format(
		len(found_paths),
		"\n".join(found_paths) if found_paths else "No matches found."
	)


@mcp.tool()
async def filesystem__grep(
	pattern: str, 
	path: Optional[str] = None, 
	max_depth: int = 10,
) -> str:
	"""
	Searches for a regex pattern within file contents.
	Parameters:
		pattern: The regex pattern to match.
		path: The directory to search. If omitted, uses CWD.
		max_depth: Maximum recursion depth.
	"""
	verified_path = _resolve_and_verify_path(path)
	root_path = Path(verified_path)
	regex = re.compile(pattern)
	matches = []
	
	for root, dirs, files in os.walk(root_path):
		depth = root[len(str(root_path)):].count(os.sep)
		if depth > max_depth:
			dirs[:] = []
			continue
		
		for f in files:
			full_path = str(Path(root) / f)
			try:
				with open(full_path, "r", encoding="utf-8", errors="ignore") as file_handle:
					for i, line in enumerate(file_handle, 1):
						if regex.search(line):
							matches.append({
								"path": full_path,
								"line": i,
								"snippet": line.strip(),
							})
			except (OSError, IOError):
				continue
	
	return str(GrepResult(matches))


@mcp.tool()
async def filesystem__find(
	pattern: str, 
	path: Optional[str] = None, 
	max_depth: int = 10,
) -> str:
	"""
	Searches for files and directories by name using regex.
	Parameters:
		pattern: The regex pattern to match against the name.
		path: The directory to search. If omitted, uses CWD.
		max_depth: Maximum recursion depth.
	"""
	verified_path = _resolve_and_verify_path(path)
	root_path = Path(verified_path)
	regex = re.compile(pattern)
	found_paths = []
	
	for root, dirs, files in os.walk(root_path):
		depth = root[len(str(root_path)):].count(os.sep)
		if depth > max_depth:
			dirs[:] = []
			continue
		
		for d in dirs:
			if regex.search(d):
				found_paths.append(str(Path(root) / d))
		
		for f in files:
			if regex.search(f):
				found_paths.append(str(Path(root) / f))
	
	return str(FindResult(found_paths))


@mcp.tool()
async def filesystem__list_allowed_directories() -> List[str]:
	"""Lists all directories that the server is allowed to access."""
	return list(allowed_directories)


@mcp.tool()
async def filesystem__get_documentation() -> str:
	"""Retrieves the server's documentation."""
	try:
		readme_path = Path(__file__).parent / "readme.md"
		with open(readme_path, "r", encoding="utf-8") as f:
			return f.read()
	except Exception as e:
		return "Documentation currently unavailable: {0}".format(str(e))
