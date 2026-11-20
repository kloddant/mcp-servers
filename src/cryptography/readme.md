# Cryptography MCP Server

A high-performance Model Context Protocol (MCP) server providing a secure wrapper around the Python `cryptography` module. This server implements a **Resource Handle Pattern**, meaning all binary data (keys, ciphertexts, signatures) are stored in a secure server-side registry and referenced by UUIDs to prevent sensitive raw bytes from leaking into the LLM context.

## 🔑 Key Management

### `generate_symmetric_key`
- **Purpose**: Generates a fresh, cryptographically strong symmetric key for use with Fernet (AES-128 in CBC mode with HMAC authentication).
- **Parameters**: None.
- **Produces**: A UUID handle to the generated key.

### `generate_asymmetric_key`
- **Purpose**: Generates a public/private key pair using the specified algorithm.
- **Parameters**: 
    - `algorithm`: The algorithm to use (`'Ed25519'` for signatures, `'X25519'` for encryption, or `'RSA'` for both).
    - `key_size`: (RSA only) The length of the key in bits (default `4096`).
    - `public_exponent`: (RSA only) The public exponent (default `65537`).
- **Produces**: A dictionary containing UUID handles for both the `private_key_id` and the `public_key_id`.

### `load_asymmetric_key`
- **Purpose**: Imports an existing asymmetric key from a PEM-encoded string into the server's memory.
- **Parameters**: 
    - `key_pem`: The PEM-formatted string of the key.
    - `private`: Boolean indicating if the key is a private key (`True`) or public key (`False`).
- **Produces**: A UUID handle to the loaded key object.

### `serialize`
- **Purpose**: Converts a binary resource (key, ciphertext, etc.) stored in the server into a human-readable string.
- **Parameters**: 
    - `id`: The UUID handle of the object to serialize.
    - `encoding`: The character encoding to use (default `'utf-8'`).
    - `errors`: How to handle decoding errors (`'strict'`, `'replace'`, or `'ignore'`).
- **Produces**: The decoded string representation of the binary data.

---

## 📦 Data Handling

### `encode`
- **Purpose**: Converts a plaintext string into bytes and stores it in the server's memory. This is the required first step before encrypting, signing, or hashing a string.
- **Parameters**: 
    - `plaintext`: The string to encode.
    - `encoding`: The character encoding to use (default `'utf-8'`).
    - `errors`: How to handle encoding errors.
- **Produces**: A UUID handle to the resulting bytes.

### `decode`
- **Purpose**: Converts a stored byte sequence back into a plaintext string.
- **Parameters**: 
    - `value_id`: The UUID handle of the bytes to decode.
    - `encoding`: The character encoding to use (default `'utf-8'`).
    - `errors`: How to handle decoding errors.
- **Produces**: A UUID handle to the resulting plaintext string.

---

## 🔒 Symmetric Encryption

### `symmetric_encrypt`
- **Purpose**: Encrypts data using a symmetric key. This provides both confidentiality and authenticity (via Fernet).
- **Parameters**: 
    - `key_id`: The UUID handle of the symmetric key.
    - `value_id`: The UUID handle of the bytes to encrypt.
- **Produces**: A UUID handle to the resulting ciphertext.

### `symmetric_decrypt`
- **Purpose**: Decrypts ciphertext using a symmetric key.
- **Parameters**: 
    - `key_id`: The UUID handle of the symmetric key.
    - `value_id`: The UUID handle of the ciphertext to decrypt.
- **Produces**: A UUID handle to the resulting plaintext bytes.

---

## 🗝️ Asymmetric Encryption

### `asymmetric_encrypt`
- **Purpose**: Encrypts data using a public key. Uses HPKE for X25519 keys and OAEP padding for RSA keys.
- **Parameters**: 
    - `public_key_id`: The UUID handle of the public key.
    - `value_id`: The UUID handle of the bytes to encrypt.
- **Produces**: A UUID handle to the resulting ciphertext.

### `asymmetric_decrypt`
- **Purpose**: Decrypts ciphertext using a private key.
- **Parameters**: 
    - `private_key_id`: The UUID handle of the private key.
    - `value_id`: The UUID handle of the ciphertext to decrypt.
- **Produces**: A UUID handle to the resulting plaintext bytes.

---

## ✍️ Identity & Integrity

### `sign`
- **Purpose**: Creates a digital signature for a piece of data to prove its origin and integrity.
- **Parameters**: 
    - `private_key_id`: The UUID handle of the private key.
    - `value_id`: The UUID handle of the data to sign.
- **Produces**: A UUID handle to the resulting signature bytes.

### `verify`
- **Purpose**: Verifies a digital signature using a public key to ensure the data has not been tampered with.
- **Parameters**: 
    - `public_key_id`: The UUID handle of the public key.
    - `value_id`: The UUID handle of the original data.
    - `signature_id`: The UUID handle of the signature to verify.
- **Produces**: A string confirming if the signature is `"Verified"` or `"Invalid"`.

### `hash_data`
- **Purpose**: Creates a cryptographic hash (fingerprint) of a piece of data.
- **Parameters**: 
    - `value_id`: The UUID handle of the data to hash.
    - `algorithm`: The hashing algorithm to use (e.g., `'sha256'`, `'sha512'`, `'md5'`).
- **Produces**: A UUID handle to the resulting hash digest.

---

## 🔑 Password-Based Keys

### `generate_salt`
- **Purpose**: Generates a cryptographically strong random salt, which is required to safely derive keys from passwords.
- **Parameters**: 
    - `length`: The length of the salt in bytes (default `16`).
- **Produces**: A UUID handle to the generated salt.

### `derive_key_from_password`
- **Purpose**: Uses PBKDF2 to transform a human-readable password and a salt into a strong symmetric key.
- **Parameters**: 
    - `password`: The plaintext password string.
    - `salt_id`: The UUID handle of the salt to use.
- **Produces**: A UUID handle to the resulting symmetric key.
