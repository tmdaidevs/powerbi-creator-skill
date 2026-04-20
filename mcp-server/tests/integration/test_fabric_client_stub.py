import os

import pytest

from src.fabric_client.client import FabricApiClient


@pytest.mark.integration
def test_fabric_client_list_workspaces_stub():
    """Integration stub: requires valid PBIR_MCP_* environment and live Fabric tenant."""
    if os.getenv("RUN_LIVE_FABRIC_TESTS", "false").lower() != "true":
        pytest.skip("Set RUN_LIVE_FABRIC_TESTS=true to execute live integration tests")

    client = FabricApiClient()
    workspaces = client.list_workspaces()
    assert isinstance(workspaces, list)
