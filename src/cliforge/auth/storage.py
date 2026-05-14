"""Credential storage backed by ~/.cliforge/credentials.json."""

import json
import logging
import stat
from pathlib import Path

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = "credentials.json"


class CredentialStorage:
    def __init__(self, base_dir: Path) -> None:
        self._path = base_dir / CREDENTIALS_FILE

    def load_all(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load credentials: %s", exc)
            return {}

    def save(self, namespace: str, credentials: dict) -> None:
        all_creds = self.load_all()
        all_creds[namespace] = credentials
        self._path.write_text(json.dumps(all_creds, indent=2), encoding="utf-8")
        self._path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def get(self, namespace: str) -> dict:
        return self.load_all().get(namespace, {})

    def delete(self, namespace: str) -> None:
        all_creds = self.load_all()
        all_creds.pop(namespace, None)
        self._path.write_text(json.dumps(all_creds, indent=2), encoding="utf-8")
