from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.auth.token_provider import AuthConfigurationError, TokenProvider
from src.config.settings import settings
from src.models.schemas import MCPErrorCode


class FabricApiError(RuntimeError):
    def __init__(self, message: str, code: MCPErrorCode, status_code: int | None = None, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.payload = payload or {}


@dataclass
class AsyncOperationState:
    status: str
    location: str | None = None
    payload: dict[str, Any] | None = None


class FabricApiClient:
    def __init__(self, token_provider: TokenProvider | None = None) -> None:
        self.token_provider = token_provider or TokenProvider()
        self._http = httpx.Client(timeout=settings.default_timeout_seconds)

    def _headers(self) -> dict[str, str]:
        try:
            token = self.token_provider.get_token()
        except AuthConfigurationError as exc:
            raise FabricApiError(str(exc), MCPErrorCode.AUTH_FAILED) from exc
        return {"Authorization": f"Bearer {token.token}", "Content-Type": "application/json"}

    @retry(wait=wait_exponential(multiplier=1, min=1, max=16), stop=stop_after_attempt(settings.max_retries), reraise=True)
    def _request(self, method: str, url: str, json_payload: dict[str, Any] | None = None) -> httpx.Response:
        response = self._http.request(method, url, headers=self._headers(), json=json_payload)

        if response.status_code == 401:
            raise FabricApiError("Authentication failed for Fabric API", MCPErrorCode.AUTH_FAILED, 401)
        if response.status_code == 403:
            raise FabricApiError("Caller lacks required Fabric/Power BI scope", MCPErrorCode.FORBIDDEN_SCOPE, 403)
        if response.status_code == 429:
            raise FabricApiError("Fabric API throttling occurred", MCPErrorCode.THROTTLED_RETRYABLE, 429)
        if response.status_code >= 500:
            raise FabricApiError("Transient Fabric API server error", MCPErrorCode.TRANSIENT_UPSTREAM_FAILURE, response.status_code)
        if response.status_code >= 400:
            raise FabricApiError(
                f"Fabric API request failed with status {response.status_code}: {response.text}",
                MCPErrorCode.VALIDATION_FAILED,
                response.status_code,
            )
        return response

    def list_workspaces(self) -> list[dict[str, Any]]:
        url = f"{settings.powerbi_api_base_url}/groups"
        return self._request("GET", url).json().get("value", [])

    def list_reports(self, workspace_id: str) -> list[dict[str, Any]]:
        url = f"{settings.powerbi_api_base_url}/groups/{workspace_id}/reports"
        return self._request("GET", url).json().get("value", [])

    def get_report_metadata(self, workspace_id: str, report_id: str) -> dict[str, Any]:
        url = f"{settings.powerbi_api_base_url}/groups/{workspace_id}/reports/{report_id}"
        return self._request("GET", url).json()

    def get_report_definition(self, workspace_id: str, report_id: str) -> dict[str, Any]:
        url = f"{settings.fabric_api_base_url}/workspaces/{workspace_id}/reports/{report_id}/getDefinition"
        response = self._request("POST", url)
        if response.status_code == 202:
            operation_url = response.headers.get("Location")
            return {"status": "pending", "location": operation_url}
        return response.json()

    def poll_operation(self, operation_url: str) -> AsyncOperationState:
        response = self._request("GET", operation_url)
        payload = response.json()
        result_location = response.headers.get("Location")
        return AsyncOperationState(status=payload.get("status", "Unknown"), location=result_location or operation_url, payload=payload)

    def wait_for_operation(self, operation_url: str, timeout_seconds: int | None = None, interval_seconds: int | None = None) -> AsyncOperationState:
        import time

        timeout_seconds = timeout_seconds or settings.async_poll_timeout_seconds
        interval_seconds = interval_seconds or settings.async_poll_interval_seconds
        deadline = time.time() + timeout_seconds
        latest = AsyncOperationState(status="Unknown", location=operation_url)

        while time.time() < deadline:
            latest = self.poll_operation(operation_url)
            if latest.status.lower() in {"succeeded", "failed", "cancelled"}:
                break
            time.sleep(interval_seconds)
        else:
            raise FabricApiError(
                f"Operation polling timed out after {timeout_seconds}s",
                MCPErrorCode.ASYNC_OPERATION_PENDING,
                payload={"location": operation_url, "lastStatus": latest.status},
            )

        if latest.status.lower() == "succeeded" and latest.location and latest.location != operation_url:
            result_response = self._request("GET", latest.location)
            latest.payload = result_response.json()

        return latest

    def execute_dax_query(self, workspace_id: str, dataset_id: str, dax: str) -> list[list[Any]]:
        """Execute a DAX query against a dataset and return rows."""
        url = f"{settings.powerbi_api_base_url}/groups/{workspace_id}/datasets/{dataset_id}/executeQueries"
        payload = {
            "queries": [{"query": dax}],
            "serializerSettings": {"includeNulls": True},
        }
        response = self._request("POST", url, json_payload=payload)
        data = response.json()
        tables = data.get("results", [{}])[0].get("tables", [])
        if not tables:
            return []
        return tables[0].get("rows", [])

    def update_report_definition(self, workspace_id: str, report_id: str, definition_parts: dict[str, Any]) -> dict[str, Any]:
        url = f"{settings.fabric_api_base_url}/workspaces/{workspace_id}/reports/{report_id}/updateDefinition"
        response = self._request("POST", url, json_payload=definition_parts)
        if response.status_code == 202:
            return {"status": "pending", "location": response.headers.get("Location")}
        return response.json()
