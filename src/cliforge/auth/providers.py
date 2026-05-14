"""Pluggable authentication providers."""

import os
from typing import Protocol, runtime_checkable


@runtime_checkable
class CredentialProvider(Protocol):
    async def get(self, namespace: str) -> dict[str, str]: ...


class BearerTokenProvider:
    def __init__(self, token: str) -> None:
        self._token = token

    async def get(self, namespace: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}


class ApiKeyProvider:
    def __init__(self, key: str, header_name: str = "X-API-Key") -> None:
        self._key = key
        self._header = header_name

    async def get(self, namespace: str) -> dict[str, str]:
        return {self._header: self._key}


class EnvVarProvider:
    """Reads credentials from environment variables. Env var name: {NAMESPACE_upper}_TOKEN or {NAMESPACE_upper}_API_KEY."""

    async def get(self, namespace: str) -> dict[str, str]:
        prefix = namespace.upper().replace("-", "_")
        token = os.environ.get(f"{prefix}_TOKEN") or os.environ.get(f"{prefix}_BEARER_TOKEN")
        if token:
            return {"Authorization": f"Bearer {token}"}
        api_key = os.environ.get(f"{prefix}_API_KEY")
        if api_key:
            return {"X-API-Key": api_key}
        return {}


class NoAuthProvider:
    async def get(self, namespace: str) -> dict[str, str]:
        return {}
