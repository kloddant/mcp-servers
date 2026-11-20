import uuid, hashlib, os, base64, dill, tempfile
from mcp.server import MCPServer
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import padding, ed25519, x25519, rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.hpke import Suite, KEM, KDF, AEAD
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import serialization
from typing import Literal
from pathlib import Path

DEFAULT_HPKE_SUITE = Suite(KEM.X25519, KDF.HKDF_SHA256, AEAD.AES_128_GCM)

mcp = MCPServer("Cryptography")


objects: dict[str, object] = {}


@mcp.tool()
def cryptography__generate_symmetric_key() -> str:
	"""
	Purpose: Generates a fresh, cryptographically strong symmetric key for use with Fernet.
	Parameters: None.
	Produces: A UUID handle to the generated key.
	"""
	key = Fernet.generate_key()
	id = str(uuid.uuid4())
	objects[id] = key
	return id


@mcp.tool()
def cryptography__generate_asymmetric_key(algorithm: Literal['Ed25519', 'X25519', 'RSA'] = 'Ed25519', key_size: int = 4096, public_exponent: int = 65537) -> dict[str, str]:
	"""
	Purpose: Generates a public/private key pair using the specified algorithm.
	Parameters: algorithm (Ed25519, X25519, RSA), key_size (int), public_exponent (int).
	Produces: A dictionary containing UUID handles for both the private_key_id and public_key_id.
	"""
	generators = {
		'Ed25519': lambda: ed25519.Ed25519PrivateKey.generate(),
		'X25519': lambda: x25519.X25519PrivateKey.generate(),
		'RSA': lambda: rsa.generate_private_key(public_exponent=public_exponent, key_size=key_size),
	}
	
	generator = generators.get(algorithm)
	if not generator:
		raise ValueError(f"Unsupported algorithm: {algorithm}")
	
	private_key = generator()
	public_key = private_key.public_key()
	
	priv_id = str(uuid.uuid4())
	pub_id = str(uuid.uuid4())
	
	objects[priv_id] = private_key
	objects[pub_id] = public_key
	
	return {
		"private_key_id": priv_id,
		"public_key_id": pub_id
	}


@mcp.tool()
def cryptography__load_asymmetric_key(key_pem: str, private: bool = True) -> str:
	"""
	Purpose: Imports a PEM-encoded asymmetric key into the server's memory.
	Parameters: key_pem (str), private (bool).
	Produces: A UUID handle to the loaded key object.
	"""
	try:
		key_bytes = key_pem.encode('utf-8')
		if private:
			# Load private key (password=None assumes the PEM is not encrypted)
			key = serialization.load_pem_private_key(key_bytes, password=None)
		else:
			# Load public key
			key = serialization.load_pem_public_key(key_bytes)
		
		key_id = str(uuid.uuid4())
		objects[key_id] = key
		return key_id
	except Exception as e:
		return f"Error: Invalid PEM key. {str(e)}"


@mcp.tool()
def cryptography__serialize(id: str, encoding: str = 'utf-8', errors: Literal['strict', 'replace', 'ignore'] = 'ignore') -> str:
	"""
	Purpose: Converts a binary resource stored in the server into a human-readable string.
	Parameters: id (UUID), encoding (str), errors (Literal).
	Produces: The decoded string representation of the binary data.
	"""
	if id not in objects:
		return ""
	obj = objects[id]
	if isinstance(obj, bytes):
		return obj.decode(encoding, errors=errors)
	if isinstance(obj, str):
		return obj
	return str(obj)
	

@mcp.tool()
def cryptography__encode(plaintext: str, encoding: str = 'utf-8', errors: Literal['strict', 'replace', 'ignore'] = 'ignore') -> str:
	"""
	Purpose: Converts a plaintext string into bytes and stores it in the server's memory.
	Parameters: plaintext (str), encoding (str), errors (Literal).
	Produces: A UUID handle to the resulting bytes.
	"""
	id = str(uuid.uuid4())
	objects[id] = plaintext.encode(encoding, errors=errors)
	return id


@mcp.tool()
def cryptography__decode(value_id: str, encoding: str = 'utf-8', errors: Literal['strict', 'replace', 'ignore'] = 'ignore') -> str:
	"""
	Purpose: Converts a stored byte sequence back into a plaintext string.
	Parameters: value_id (UUID), encoding (str), errors (Literal).
	Produces: A UUID handle to the resulting plaintext string.
	"""
	if value_id not in objects:
		return ""
	encoded_bytes = objects[value_id]
	id = str(uuid.uuid4())
	objects[id] = encoded_bytes.decode(encoding, errors=errors)
	return id


# --- Symmetric ---
@mcp.tool()
def cryptography__symmetric_encrypt(key_id: str, value_id: str) -> str:
	"""
	Purpose: Encrypts data using a symmetric key. Provides both confidentiality and authenticity.
	Parameters: key_id (UUID), value_id (UUID).
	Produces: A UUID handle to the resulting ciphertext.
	"""
	if key_id not in objects:
		return ""
	if value_id not in objects:
		return ""
	key = objects[key_id]
	f = Fernet(key)
	value = objects[value_id]
	id = str(uuid.uuid4())
	token = f.encrypt(value)
	objects[id] = token
	return id


@mcp.tool()
def cryptography__symmetric_decrypt(key_id: str, value_id: str) -> str:
	"""
	Purpose: Decrypts ciphertext using a symmetric key.
	Parameters: key_id (UUID), value_id (UUID).
	Produces: A UUID handle to the resulting plaintext bytes.
	"""
	if key_id not in objects:
		return ""
	if value_id not in objects:
		return ""
	key = objects[key_id]
	f = Fernet(key)
	value = objects[value_id]
	decrypted_token = f.decrypt(value)
	id = str(uuid.uuid4())
	objects[id] = decrypted_token
	return id


@mcp.tool()
def cryptography__asymmetric_encrypt(public_key_id: str, value_id: str) -> str:
	"""
	Purpose: Encrypts data using a public key (HPKE for X25519, OAEP for RSA).
	Parameters: public_key_id (UUID), value_id (UUID).
	Produces: A UUID handle to the resulting ciphertext.
	"""
	# 1. Retrieve the public key
	public_key = objects.get(public_key_id)
	if public_key is None:
		return "Error: Public Key ID not found."
	
	# 2. Retrieve the data to encrypt
	data = objects.get(value_id)
	if data is None:
		return "Error: Value ID not found."
	
	# Ensure data is bytes (in case the LLM bypassed encode())
	if isinstance(data, str):
		data = data.encode('utf-8')
	
	try:
		# 3. Handle RSA Encryption (Legacy/Standard)
		if hasattr(public_key, 'encrypt'): 
			ciphertext = public_key.encrypt(
				data,
				padding.OAEP(
					mgf=padding.MGF1(algorithm=hashes.SHA256()),
					algorithm=hashes.SHA256(),
					label=None
				)
			)
		
		# 4. Handle X25519 Encryption (Modern HPKE)
		else:
			ciphertext = DEFAULT_HPKE_SUITE.encrypt(data, public_key, info=b"")
			
	except ValueError as e:
		return f"Error: Data too large for this key size. {str(e)}"
	except Exception as e:
		return f"Error: Encryption failed. {str(e)}"
	
	# 5. Store result in objects and return UUID
	ciphertext_id = str(uuid.uuid4())
	objects[ciphertext_id] = ciphertext
	return ciphertext_id


@mcp.tool()
def cryptography__asymmetric_decrypt(private_key_id: str, value_id: str) -> str:
	"""
	Purpose: Decrypts ciphertext using a private key (HPKE for X25519, OAEP for RSA).
	Parameters: private_key_id (UUID), value_id (UUID).
	Produces: A UUID handle to the resulting plaintext bytes.
	"""
	# 1. Retrieve the private key
	private_key = objects.get(private_key_id)
	if private_key is None:
		return "Error: Private Key ID not found."
	
	# 2. Retrieve the ciphertext
	ciphertext = objects.get(value_id)
	if ciphertext is None:
		return "Error: Ciphertext ID not found."
	
	# Ensure ciphertext is bytes
	if isinstance(ciphertext, str):
		ciphertext = ciphertext.encode('utf-8')
	
	try:
		# 3. Handle RSA Decryption
		if hasattr(private_key, 'decrypt'):
			plaintext = private_key.decrypt(
				ciphertext,
				padding.OAEP(
					mgf=padding.MGF1(algorithm=hashes.SHA256()),
					algorithm=hashes.SHA256(),
					label=None
				)
			)
		
		# 4. Handle X25519 Decryption (Modern HPKE)
		else:
			plaintext = DEFAULT_HPKE_SUITE.decrypt(ciphertext, private_key, info=b"")
			
	except ValueError as e:
		return f"Error: Decryption failed (possibly wrong key or corrupted data). {str(e)}"
	except Exception as e:
		return f"Error: An unexpected error occurred. {str(e)}"
	
	# 5. Store result in objects and return UUID
	plaintext_id = str(uuid.uuid4())
	objects[plaintext_id] = plaintext
	return plaintext_id


# --- Identity & Integrity ---
@mcp.tool()
def cryptography__sign(private_key_id: str, value_id: str) -> str:
	"""
	Purpose: Creates a digital signature for a piece of data to prove origin and integrity.
	Parameters: private_key_id (UUID), value_id (UUID).
	Produces: A UUID handle to the resulting signature bytes.
	"""
	# 1. Retrieve the private key and the data to sign
	private_key = objects.get(private_key_id)
	data = objects.get(value_id)
	
	if private_key is None or data is None:
		return "Error: Private Key or Value ID not found."
	
	# Ensure data is bytes
	if isinstance(data, str):
		data = data.encode('utf-8')
	
	try:
		# 2. Handle Ed25519 Signing
		if hasattr(private_key, 'sign'): # Ed25519 keys have a .sign() method
			signature = private_key.sign(data)
		
		# 3. Handle RSA Signing (using PSS padding)
		else:
			signature = private_key.sign(
				data,
				padding.PSS(
					mgf=padding.MGF1(algorithm=hashes.SHA256()),
					salt_length=padding.PSS.MAX_LENGTH
				),
				hashes.SHA256()
			)
			
	except Exception as e:
		return f"Error: Signing failed. {str(e)}"
	
	# 4. Store signature and return UUID
	sig_id = str(uuid.uuid4())
	objects[sig_id] = signature
	return sig_id


@mcp.tool()
def cryptography__verify(public_key_id: str, value_id: str, signature_id: str) -> str:
	"""
	Purpose: Verifies a digital signature using a public key.
	Parameters: public_key_id (UUID), value_id (UUID), signature_id (UUID).
	Produces: A string confirming if the signature is "Verified" or "Invalid".
	"""
	# 1. Retrieve the public key, the original data, and the signature
	public_key = objects.get(public_key_id)
	data = objects.get(value_id)
	signature = objects.get(signature_id)
	
	if any(x is None for x in [public_key, data, signature]):
		return "Error: One or more IDs not found."
	
	# Ensure data is bytes
	if isinstance(data, str):
		data = data.encode('utf-8')
	
	try:
		# 2. Handle Ed25519 Verification
		if hasattr(public_key, 'verify'):
			public_key.verify(signature, data)
		
		# 3. Handle RSA Verification (using PSS padding)
		else:
			public_key.verify(
				signature,
				data,
				padding.PSS(
					mgf=padding.MGF1(algorithm=hashes.SHA256()),
					salt_length=padding.PSS.MAX_LENGTH
				),
				hashes.SHA256()
			)
		return "Verified: The signature is valid."
	except Exception:
		return "Invalid: The signature does not match the data or key."



@mcp.tool()
def cryptography__hash(value_id: str, algorithm: Literal['md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512', 'sha3_224', 'sha3_256', 'sha3_384', 'sha3_512'] = "sha256") -> str:
	"""
	Purpose: Creates a cryptographic hash (fingerprint) of a piece of data.
	Parameters: value_id (UUID), algorithm (Literal).
	Produces: A UUID handle to the resulting hash digest.
	"""
	if not value_id in objects:
		return ""
	value = objects[value_id]
	if not isinstance(value, bytes):
		return ""
	m = getattr(hashlib, algorithm.lower())()
	m.update(value)
	id = str(uuid.uuid4())
	objects[id] = m.digest()
	return id


@mcp.tool()
def cryptography__derive_key_from_password(password: str, salt_id: str) -> str:
	"""
	Purpose: Uses PBKDF2 to transform a password and salt into a strong symmetric key.
	Parameters: password (str), salt_id (UUID).
	Produces: A UUID handle to the resulting symmetric key.
	"""
	# 1. Retrieve the salt
	salt = objects.get(salt_id)
	if salt is None:
		return "Error: Salt ID not found."
	
	# Ensure salt is bytes
	if isinstance(salt, str):
		salt = salt.encode('utf-8')
	
	try:
		# 2. Setup PBKDF2
		# We use SHA256 and 600,000 iterations (current OWASP recommendation)
		kdf = PBKDF2HMAC(
			algorithm=hashes.SHA256(),
			length=32,
			salt=salt,
			iterations=600000,
		)
		
		raw_key = kdf.derive(password.encode('utf-8'))
		fernet_key = base64.urlsafe_b64encode(raw_key)
		
		# 4. Store the resulting key and return UUID
		key_id = str(uuid.uuid4())
		objects[key_id] = fernet_key
		return key_id
	except Exception as e:
		return f"Error: Key derivation failed. {str(e)}"


@mcp.tool()
def cryptography__generate_salt(length: int = 16) -> str:
	"""
	Purpose: Generates a cryptographically strong random salt.
	Parameters: length (int).
	Produces: A UUID handle to the generated salt.
	"""
	salt = os.urandom(length)
	salt_id = str(uuid.uuid4())
	objects[salt_id] = salt
	return salt_id


@mcp.tool()
def cryptography__base64_encode(value_id: str) -> str:
	"""
	Purpose: Converts binary data stored in the server into a Base64 encoded string.
	Parameters: value_id (UUID).
	Produces: The Base64 encoded string representation of the binary data.
	"""
	if value_id not in objects:
		return "Error: Value ID not found."
	
	obj = objects[value_id]
	if not isinstance(obj, bytes):
		return "Error: The referenced object is not binary data."
	
	try:
		return base64.b64encode(obj).decode('utf-8')
	except UnicodeDecodeError as e:
		return "Error: Failed to decode Base64 result to UTF-8. {}".format(str(e))


@mcp.tool()
def cryptography__base64_decode(base64_string: str) -> str:
	"""
	Purpose: Decodes a Base64 encoded string and stores the resulting binary data in the server.
	Parameters: base64_string (str).
	Produces: A UUID handle to the resulting binary data.
	"""
	try:
		binary_data = base64.b64decode(base64_string)
	except Exception as e:
		return "Error: Invalid Base64 string. {}".format(str(e))
	
	id = str(uuid.uuid4())
	objects[id] = binary_data
	return id


@mcp.tool()
async def cryptography__get_documentation() -> str:
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