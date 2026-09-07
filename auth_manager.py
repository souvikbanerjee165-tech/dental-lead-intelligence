"""
Enterprise Authentication & Access Control Manager.
Provides PBKDF2-HMAC-SHA256 password hashing, signed time-limited session tokens,
and seamless zero-friction local operation with optional production lockdown.
"""

import os
import hmac
import time
import base64
import hashlib
import secrets
import logging
from typing import Dict, Any, Optional, Tuple

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger("auth_manager")

# Master secret key for session HMAC signing
_DEFAULT_SECRET = os.getenv("AUTH_SECRET_KEY") or "apex-dental-secret-key-salt-7889123049"
SESSION_DURATION_SEC = int(os.getenv("AUTH_SESSION_HOURS", "24")) * 3600

bearer_scheme = HTTPBearer(auto_error=False)


class AuthManager:
    """Manages password verification, signed session issuance, and route protection."""

    def __init__(self, secret_key: str = _DEFAULT_SECRET):
        self.secret_key = secret_key.encode("utf-8")

    @staticmethod
    def hash_password(password: str, salt: Optional[bytes] = None) -> str:
        """Derives a PBKDF2-HMAC-SHA256 hash with 100,000 rounds and random salt."""
        if not salt:
            salt = secrets.token_bytes(16)
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            100000
        )
        salt_b64 = base64.b64encode(salt).decode("utf-8")
        hash_b64 = base64.b64encode(derived).decode("utf-8")
        return f"pbkdf2_sha256$100000${salt_b64}${hash_b64}"

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verifies a plain password against a PBKDF2 hash using constant-time comparison."""
        try:
            parts = hashed.split("$")
            if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
                # Fallback for plain-string match if user set a plain PIN in env for simplicity
                return hmac.compare_digest(password, hashed)
            
            iterations = int(parts[1])
            salt = base64.b64decode(parts[2].encode("utf-8"))
            expected_derived = base64.b64decode(parts[3].encode("utf-8"))

            derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(derived, expected_derived)
        except Exception as e:
            logger.warning(f"Password verification error: {e}")
            return False

    def create_session_token(self, username: str = "admin", duration_sec: int = SESSION_DURATION_SEC) -> str:
        """Issues a cryptographically signed, timestamped session token."""
        expires_at = int(time.time()) + duration_sec
        nonce = secrets.token_hex(4)
        payload = f"{username}:{expires_at}:{nonce}"
        
        signature = hmac.new(
            self.secret_key,
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        token = f"{payload}:{signature}"
        return base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8")

    def validate_session_token(self, token: str) -> Tuple[bool, Optional[str]]:
        """Validates token signature and expiration timestamp."""
        if not token:
            return False, "Token missing"

        try:
            decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
            parts = decoded.split(":")
            if len(parts) != 4:
                return False, "Malformed token structure"

            username, expires_str, nonce, signature = parts
            payload = f"{username}:{expires_str}:{nonce}"
            expires_at = int(expires_str)

            if time.time() > expires_at:
                return False, "Session token has expired"

            expected_signature = hmac.new(
                self.secret_key,
                payload.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                return False, "Invalid cryptographic signature"

            return True, username
        except Exception as e:
            return False, f"Token validation failed: {str(e)}"

    @staticmethod
    def is_auth_required() -> bool:
        """Determines whether authentication is currently enforced."""
        env_req = os.getenv("REQUIRE_AUTH", "false").lower()
        if env_req in ["1", "true", "yes"]:
            return True
        # Also check if password or pin is set in env
        if os.getenv("AUTH_PASSWORD") or os.getenv("AUTH_PIN"):
            return True
        return False

    @staticmethod
    def get_configured_password() -> Optional[str]:
        """Returns the configured admin password or PIN."""
        return os.getenv("AUTH_PASSWORD") or os.getenv("AUTH_PIN") or "apex2026"


# Global instance
auth_manager = AuthManager()


async def verify_auth_dependency(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> Optional[str]:
    """
    FastAPI dependency for protecting sensitive endpoints.
    Allows pass-through if REQUIRE_AUTH=false.
    Checks Bearer token or session_token cookie.
    """
    if not auth_manager.is_auth_required():
        return "local_dev_user"

    token = None
    if credentials:
        token = credentials.credentials
    elif "session_token" in request.cookies:
        token = request.cookies.get("session_token")
    elif "x-session-token" in request.headers:
        token = request.headers.get("x-session-token")

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide a valid session token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    valid, username_or_err = auth_manager.validate_session_token(token)
    if not valid:
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {username_or_err}",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return username_or_err
