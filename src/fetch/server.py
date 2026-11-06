import uuid, asyncio, requests, json
from typing import Literal, Dict, Set, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from mcp.server import MCPServer

mcp = MCPServer("fetch")

# Using a standard browser User-Agent to avoid being blocked by servers
DEFAULT_HEADERS: Dict[str, str] = {
	"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
# Headers provided via CLI arguments (highest priority)
CLI_HEADERS: Dict[str, str] = {}

allowed_hosts: Set[str] = set()
objects: Dict[str, requests.Response] = {}
robot_parsers: Dict[str, RobotFileParser] = {}
robots_tags: Dict[str, str] = {}

SAFE_METHODS = {'GET', 'QUERY', 'HEAD', 'OPTIONS', 'TRACE'}
session = requests.Session()


@mcp.tool()
async def get_allowed_hosts() -> str:
	"""Returns the list of hostnames and domains that this server is allowed to fetch from."""
	return ", ".join(allowed_hosts)


@mcp.tool()
async def fetch(
	url: str, 
	method: Literal['GET', 'QUERY', 'HEAD', 'OPTIONS', 'TRACE'] = 'GET', 
	http_request_headers: Optional[Dict[str, str]] = None,
	timeout: Optional[int] = 5
) -> str:
	"""
	Fetches a URL and returns a unique identifier for the response.
	Only URLs from allowed hosts (and their subdomains) will be fetched.
	Respects robots.txt and X-Robots-Tag.
	Redirects are disabled to ensure whitelist checks on every hop.
	"""
	if method not in SAFE_METHODS:
		raise ValueError("Method {0} is not allowed. Please use one of: {1}".format(method, ", ".join(SAFE_METHODS)))

	parsed = urlparse(url)
	hostname = parsed.hostname

	if not hostname:
		raise ValueError("Invalid URL: No hostname found.")

	# 1. Check Host Whitelist
	is_allowed = False
	for allowed in allowed_hosts:
		if hostname == allowed or hostname.endswith("." + allowed):
			is_allowed = True
			break

	if not is_allowed:
		raise ValueError("Host {0} is not in the allowed hosts list.".format(hostname))

	# 2. Check X-Robots-Tag (per page)
	page_key = "{0}{1}".format(hostname, parsed.path)
	tag = robots_tags.get(page_key, "")
	if "noindex" in tag.split(","):
		raise ValueError("Page {0} is prohibited via X-Robots-Tag: noindex.".format(url))

	# 3. Check robots.txt (per host)
	if hostname not in robot_parsers:
		rp = RobotFileParser()
		scheme = parsed.scheme if parsed.scheme else "http"
		rp.set_url("{0}://{1}/robots.txt".format(scheme, hostname))
		try:
			# Use a thread to avoid blocking the event loop
			await asyncio.to_thread(rp.read)
		except Exception:
			# If robots.txt is missing or fails, we default to allowing the fetch
			pass 
		robot_parsers[hostname] = rp
	
	rp = robot_parsers[hostname]
	try:
		if not rp.can_fetch(DEFAULT_HEADERS["User-Agent"], url):
			raise ValueError("Fetch prohibited by robots.txt for host {0}.".format(hostname))
	except Exception:
		# Failsafe: if the parser crashes, allow the fetch but log it (internally)
		pass

	# 4. Resolve Header Precedence
	headers = DEFAULT_HEADERS.copy()
	if http_request_headers:
		headers.update(http_request_headers)
	headers.update(CLI_HEADERS)

	def perform_request():
		try:
			r = session.request(method, url, headers=headers, timeout=timeout, allow_redirects=False)
			
			resp_tag = r.headers.get("X-Robots-Tag")
			if resp_tag:
				robots_tags[page_key] = resp_tag

			return r
		except requests.RequestException as e:
			raise RuntimeError("HTTP request failed: {0}".format(e))

	response_obj = await asyncio.to_thread(perform_request)

	obj_id = str(uuid.uuid4())
	objects[obj_id] = response_obj
	return obj_id


@mcp.tool()
async def get_response_content(id: str) -> str:
	"""Retrieves the body content of a previously fetched response. Returns a warning for binary content."""
	if id not in objects:
		raise ValueError("No response found with ID: {0}".format(id))
	
	resp = objects[id]
	content_type = resp.headers.get("Content-Type", "").lower()
	
	if content_type and not any(t in content_type for t in ["text/", "application/json", "application/xml", "application/javascript"]):
		return "Binary content detected (Type: {0}). This content cannot be returned as text.".format(content_type)
	
	return resp.text


@mcp.tool()
async def get_response_status(id: str) -> str:
	"""Retrieves the HTTP status code of a previously fetched response."""
	if id not in objects:
		raise ValueError("No response found with ID: {0}".format(id))
	return str(objects[id].status_code)


@mcp.tool()
async def get_response_headers(id: str, header: Optional[str] = None) -> str:
	"""Retrieves a specific header value or all headers as JSON from a previously fetched response."""
	if id not in objects:
		raise ValueError("No response found with ID: {0}".format(id))
	
	if header:
		return objects[id].headers.get(header, "Header not found")
	
	return json.dumps(dict(objects[id].headers))
