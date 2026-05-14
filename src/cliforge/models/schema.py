from pydantic import BaseModel


class ConnectorConfig(BaseModel):
    type: str
    namespace: str
    source: str
    metadata: dict = {}


class RegistryEntry(BaseModel):
    connectors: list[ConnectorConfig] = []
