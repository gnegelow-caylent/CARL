"""GitHub App authentication service for generating short-lived tokens."""
import time
import jwt
import requests
from typing import Optional
from datetime import datetime, timedelta, timezone
from utils.logger import get_logger

logger = get_logger(__name__)


class GitHubAppAuth:
    """
    Handles GitHub App authentication with JWT tokens.

    Generates short-lived installation tokens (1 hour TTL) instead of
    using permanent Personal Access Tokens.
    """

    def __init__(self, app_id: str, private_key: str, installation_id: str):
        """
        Initialize GitHub App authentication.

        Args:
            app_id: GitHub App ID
            private_key: RSA private key (PEM format)
            installation_id: Installation ID for the specific organization/repo
        """
        self.app_id = app_id
        self.private_key = private_key
        self.installation_id = installation_id
        self.base_url = "https://api.github.com"

        # Cache token and expiration
        self._cached_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    def get_installation_token(self) -> str:
        """
        Get a valid installation token (generates new if expired).

        Tokens are cached and automatically refreshed when they expire.
        Installation tokens are valid for 1 hour.

        Returns:
            str: Valid GitHub installation access token
        """
        # Return cached token if still valid (with 5 min buffer)
        if self._cached_token and self._token_expires_at:
            if datetime.now(timezone.utc) < self._token_expires_at - timedelta(minutes=5):
                logger.debug("Using cached GitHub installation token")
                return self._cached_token

        # Generate new token
        logger.info("Generating new GitHub installation token")

        # Step 1: Create JWT token for app authentication
        jwt_token = self._create_jwt()

        # Step 2: Exchange JWT for installation access token
        installation_token = self._get_installation_access_token(jwt_token)

        # Cache the token
        self._cached_token = installation_token["token"]
        self._token_expires_at = datetime.fromisoformat(
            installation_token["expires_at"].replace("Z", "+00:00")
        )

        logger.info(f"New token generated, expires at {self._token_expires_at}")
        return self._cached_token

    def _create_jwt(self) -> str:
        """
        Create a JWT token for GitHub App authentication.

        JWT tokens are valid for 10 minutes and used to request installation tokens.

        Returns:
            str: Signed JWT token
        """
        # JWT payload
        now = int(time.time())
        payload = {
            # Issued at time
            "iat": now - 60,  # 60 seconds in the past to allow for clock drift
            # JWT expiration time (10 minutes maximum)
            "exp": now + (10 * 60),
            # GitHub App's identifier
            "iss": self.app_id
        }

        # Create JWT token signed with private key
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256"
        )

        return token

    def _get_installation_access_token(self, jwt_token: str) -> dict:
        """
        Exchange JWT token for installation access token.

        Args:
            jwt_token: JWT token from _create_jwt()

        Returns:
            dict: Installation token response with 'token' and 'expires_at'
        """
        url = f"{self.base_url}/app/installations/{self.installation_id}/access_tokens"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {jwt_token}",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        response = requests.post(url, headers=headers, timeout=10)

        if response.status_code != 201:
            logger.error(f"Failed to get installation token: {response.status_code} - {response.text}")
            response.raise_for_status()

        return response.json()

    def invalidate_cache(self):
        """Force regeneration of token on next request."""
        self._cached_token = None
        self._token_expires_at = None
        logger.debug("GitHub token cache invalidated")
