from __future__ import annotations

from dataclasses import dataclass

from src.config.settings import settings


class AuthConfigurationError(RuntimeError):
    pass


@dataclass
class AccessToken:
    token: str
    expires_on: int


class TokenProvider:
    """Acquires AAD access tokens using service principal, delegated, or managed identity."""

    def __init__(self) -> None:
        self._credential = None

    def _build_credential(self):
        try:
            from azure.identity import (
                ClientSecretCredential,
                DefaultAzureCredential,
                ManagedIdentityCredential,
            )
        except ImportError as exc:
            raise AuthConfigurationError(
                "azure-identity is required for token acquisition; install it in deployment image"
            ) from exc

        if settings.use_managed_identity:
            return ManagedIdentityCredential()

        if settings.tenant_id and settings.client_id and settings.client_secret:
            return ClientSecretCredential(
                tenant_id=settings.tenant_id,
                client_id=settings.client_id,
                client_secret=settings.client_secret,
            )

        return DefaultAzureCredential(exclude_interactive_browser_credential=False)

    def get_token(self, scope: str = "https://analysis.windows.net/powerbi/api/.default") -> AccessToken:
        if self._credential is None:
            self._credential = self._build_credential()
        token = self._credential.get_token(scope)
        return AccessToken(token=token.token, expires_on=token.expires_on)
