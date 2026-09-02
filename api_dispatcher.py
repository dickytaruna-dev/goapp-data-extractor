import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
import jwt
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import APIConfig, JWTConfig


@dataclass
class DispatchResult:
    success: bool
    status_code: Optional[int]
    response_body: Optional[str]
    error_message: Optional[str] = None


class APIDispatcher:
    def __init__(self, api_config: APIConfig, jwt_config: JWTConfig):
        self.api_config = api_config
        self.jwt_config = jwt_config
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=self.api_config.max_retries,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def generate_jwt_token(self, subject: str = "goapp-data-payload") -> str:
        """
        Generates a signed JWT token using configured secret, algorithm, and claims.
        If a static bearer token is provided in config, it returns that instead.
        """
        if self.jwt_config.static_token and self.jwt_config.static_token.strip():
            return self.jwt_config.static_token.strip()

        now = int(time.time())
        claims: Dict[str, Any] = {
            "iss": self.jwt_config.issuer,
            "sub": subject,
            "iat": now,
            "exp": now + self.jwt_config.expiry_seconds
        }

        if self.jwt_config.audience:
            claims["aud"] = self.jwt_config.audience

        token = jwt.encode(
            claims,
            self.jwt_config.secret,
            algorithm=self.jwt_config.algorithm
        )
        return token

    def send_json(
        self,
        payload: Dict[str, Any],
        endpoint_override: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None
    ) -> DispatchResult:
        """
        Sends JSON payload to the configured API endpoint with Authorization: Bearer <JWT>.
        """
        url = endpoint_override or self.api_config.endpoint_url
        token = self.generate_jwt_token(subject=payload.get("metadata", {}).get("brand", "goapp-data"))

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "GoAppDataExtractor/1.0"
        }
        
        if custom_headers:
            headers.update(custom_headers)

        try:
            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.api_config.timeout_seconds
            )
            
            is_success = 200 <= response.status_code < 300
            
            return DispatchResult(
                success=is_success,
                status_code=response.status_code,
                response_body=response.text[:1000],  # Truncate response preview
                error_message=None if is_success else f"HTTP error {response.status_code}: {response.text[:300]}"
            )
        except requests.exceptions.RequestException as exc:
            return DispatchResult(
                success=False,
                status_code=None,
                response_body=None,
                error_message=f"Request failed: {str(exc)}"
            )
