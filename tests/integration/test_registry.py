"""Integration tests for the registry."""

import json
from pathlib import Path

import pytest

from cliforge.models.schema import ConnectorConfig
from cliforge.models.tool import OpenApiExecution, Tool
from cliforge.registry.persistence import PersistenceManager
from cliforge.registry.store import Registry


def make_tool(namespace: str, name: str) -> Tool:
    return Tool(
        id=f"{namespace}.{name}",
        namespace=namespace,
        name=name,
        description=f"Tool {name}",
        input_schema={"type": "object"},
        execution=OpenApiExecution(
            base_url="https://api.example.com",
            path="/test",
            method="GET",
        ),
    )


def test_registry_add_connector(tmp_path):
    registry = Registry(base_dir=tmp_path)
    config = ConnectorConfig(type="openapi", namespace="test", source="./spec.yaml")
    registry.add_connector(config)
    assert registry.has_connector("test")


def test_registry_remove_connector(tmp_path):
    registry = Registry(base_dir=tmp_path)
    config = ConnectorConfig(type="openapi", namespace="test", source="./spec.yaml")
    registry.add_connector(config)
    tool = make_tool("test", "op")
    registry.cache_tools([tool])
    registry.remove_connector("test")
    assert not registry.has_connector("test")
    assert not registry.get_tools("test")


def test_registry_cache_and_get_tools(tmp_path):
    registry = Registry(base_dir=tmp_path)
    tools = [make_tool("ns", f"tool{i}") for i in range(3)]
    registry.cache_tools(tools)
    stored = registry.get_tools("ns")
    assert len(stored) == 3


def test_registry_get_tool_by_name(tmp_path):
    registry = Registry(base_dir=tmp_path)
    tool = make_tool("ns", "myop")
    registry.cache_tools([tool])
    found = registry.get_tool_by_name("ns", "myop")
    assert found is not None
    assert found.id == "ns.myop"


def test_registry_get_tool_by_name_missing(tmp_path):
    registry = Registry(base_dir=tmp_path)
    result = registry.get_tool_by_name("ns", "nope")
    assert result is None


def test_registry_persistence(tmp_path):
    """Tools and connectors survive a reload."""
    registry1 = Registry(base_dir=tmp_path)
    config = ConnectorConfig(type="openapi", namespace="test", source="./spec.yaml")
    registry1.add_connector(config)
    tool = make_tool("test", "op")
    registry1.cache_tools([tool])

    registry2 = Registry(base_dir=tmp_path)
    registry2.load()
    assert registry2.has_connector("test")
    found = registry2.get_tool_by_name("test", "op")
    assert found is not None
    assert found.id == "test.op"


def test_registry_filter_by_namespace(tmp_path):
    registry = Registry(base_dir=tmp_path)
    registry.cache_tools([make_tool("a", "x"), make_tool("b", "y")])
    a_tools = registry.get_tools("a")
    assert all(t.namespace == "a" for t in a_tools)
    assert len(a_tools) == 1


def test_persistence_manager_save_load(tmp_path):
    pm = PersistenceManager(base_dir=tmp_path)
    data = {"key": "value", "nested": {"a": 1}}
    pm.save("test.json", data)
    loaded = pm.load("test.json")
    assert loaded == data


def test_persistence_manager_missing_file(tmp_path):
    pm = PersistenceManager(base_dir=tmp_path)
    result = pm.load("nonexistent.json")
    assert result == {}
