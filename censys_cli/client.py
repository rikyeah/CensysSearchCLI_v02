"""
Client for interacting with Censys Search v2 API.
Supports Bearer (API key) and Basic (ID/secret) authentication.
Implements retry with exponential backoff for robust HTTP requests.
"""
import time
import random
from typing import Optional, Tuple, List, Dict, Any
import requests
from requests.auth import HTTPBasicAuth

DEFAULT_BASE = "https://search.censys.io/api"
ENDPOINTS = {
    "hosts": "/v2/hosts/search",
    "certificates": "/v2/certificates/search",
}

class CensysClient:
    def __init__(self, api_key: Optional[str] = None, api_id: Optional[str] = None, api_secret: Optional[str] = None,
                 org_id: Optional[str] = None, base_url: str = DEFAULT_BASE, timeout: float = 30.0, logger=None,
                 max_retries: int = 6, backoff_base: float = 0.8):
        """
        Initialise the Censys API client.
        Requires either an API key or both API ID and secret.
        """
        if not (api_key or (api_id and api_secret)):
            raise ValueError("Provide api_key OR api_id+api_secret.")
        self.api_key = api_key
        self.api_id = api_id
        self.api_secret = api_secret
        self.org_id = org_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.logger = logger
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    def _headers(self) -> Dict[str, str]:
        """Generate HTTP headers for API requests."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "censys-cli/1.0",
        }
        if self.org_id:
            headers["Censys-Organization-Id"] = str(self.org_id)
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _auth(self):
        """Return Basic authentication if no API key is provided."""
        if (self.api_id and self.api_secret) and not self.api_key:
            return HTTPBasicAuth(self.api_id, self.api_secret)
        return None

    def _request(self, method: str, path: str, json_body: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HTTP request with retry and backoff for rate limits and errors."""
        url = f"{self.base_url}{path}"
        headers = self._headers()
        auth = self._auth()
        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.request(method, url, headers=headers, auth=auth, timeout=self.timeout, json=json_body)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else (self.backoff_base * (2 ** attempt) + random.uniform(0, 0.4))
                    if self.logger:
                        self.logger.warning("rate_limited", extra={"attempt": attempt, "wait": wait})
                    time.sleep(wait)
                    continue
                if 500 <= resp.status_code < 600:
                    wait = self.backoff_base * (2 ** attempt) + random.uniform(0, 0.5)
                    if self.logger:
                        self.logger.warning("server_error", extra={"status": resp.status_code, "attempt": attempt, "wait": wait})
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                last_err = str(e)
                wait = self.backoff_base * (2 ** attempt) + random.uniform(0, 0.5)
                if self.logger:
                    self.logger.warning("request_exception", extra={"error": last_err, "attempt": attempt, "wait": wait})
                time.sleep(wait)
        raise RuntimeError(f"Request failed after {self.max_retries} retries: {last_err}")

    def search(self, index: str, query: str, per_page: int = 100, cursor: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Search the specified index with the given query."""
        if index not in ENDPOINTS:
            raise ValueError(f"Unsupported index '{index}'. Choose from: {list(ENDPOINTS.keys())}")
        body = {"q": query, "per_page": per_page}
        if cursor:
            body["cursor"] = cursor
        data = self._request("POST", ENDPOINTS[index], body)
        result = data.get("result") or {}
        hits = result.get("hits") or []
        links = data.get("links") or result.get("links") or {}
        next_cursor = links.get("next")
        return hits, next_cursor