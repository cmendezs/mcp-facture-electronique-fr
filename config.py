"""
Configuration et gestion OAuth2 pour la Plateforme Agréée (PA).

Gère l'obtention et le renouvellement automatique du token Bearer JWT
utilisé par le Flow Service et le Directory Service (XP Z12-013).
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

load_dotenv()

logger = logging.getLogger(__name__)


class PAConfig(BaseSettings):
    """Configuration de la Plateforme Agréée lue depuis les variables d'environnement."""

    pa_base_url_flow: str = Field(
        ...,
        description="URL de base du Flow Service (ex: https://api.flow.votre-pa.fr/flow-service)",
    )
    pa_base_url_directory: str = Field(
        ...,
        description="URL de base du Directory Service (ex: https://api.directory.votre-pa.fr/directory-service)",
    )
    pa_client_id: str = Field(..., description="Client ID OAuth2 fourni par la PA")
    pa_client_secret: str = Field(..., description="Client Secret OAuth2 fourni par la PA")
    pa_token_url: str = Field(
        ..., description="URL du endpoint token OAuth2 (ex: https://auth.votre-pa.fr/oauth/token)"
    )
    pa_oauth_scope: Optional[str] = Field(
        default=None, description="Scope OAuth2 (optionnel, selon la PA)"
    )
    http_timeout: float = Field(default=30.0, description="Timeout HTTP en secondes")
    debug: bool = Field(default=False, description="Activer les logs de débogage")

    @field_validator("pa_base_url_flow", "pa_base_url_directory", "pa_token_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


class TokenCache:
    """
    Cache du token OAuth2 avec gestion de l'expiration.

    Le token est renouvelé automatiquement 30 secondes avant son expiration
    pour éviter les rejets 401 en cours de requête.
    """

    EXPIRY_MARGIN_SECONDS = 30

    def __init__(self) -> None:
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0

    def is_valid(self) -> bool:
        """Retourne True si le token en cache est encore valide."""
        return (
            self._access_token is not None
            and time.monotonic() < self._expires_at - self.EXPIRY_MARGIN_SECONDS
        )

    def set(self, access_token: str, expires_in: int) -> None:
        """Stocke un nouveau token avec sa durée de validité."""
        self._access_token = access_token
        self._expires_at = time.monotonic() + expires_in
        logger.debug("Token OAuth2 renouvelé, expire dans %ds", expires_in)

    def get(self) -> Optional[str]:
        """Retourne le token courant ou None s'il est expiré."""
        if self.is_valid():
            return self._access_token
        return None

    def invalidate(self) -> None:
        """Force le renouvellement au prochain appel."""
        self._access_token = None
        self._expires_at = 0.0


class OAuthClient:
    """
    Client OAuth2 partagé entre Flow Service et Directory Service.

    Utilise le flux client_credentials (machine-to-machine) conformément
    aux exigences de l'Annexe A/B XP Z12-013.
    """

    def __init__(self, config: PAConfig) -> None:
        self._config = config
        self._cache = TokenCache()

    async def get_token(self) -> str:
        """
        Retourne un Bearer token valide.

        Si le token en cache est encore valide, le retourne directement.
        Sinon, en obtient un nouveau auprès du serveur d'autorisation de la PA.

        Raises:
            httpx.HTTPStatusError: En cas d'erreur HTTP lors de l'obtention du token.
            ValueError: Si la réponse ne contient pas de access_token.
        """
        cached = self._cache.get()
        if cached:
            return cached

        return await self._fetch_token()

    async def _fetch_token(self) -> str:
        """Appelle le endpoint token OAuth2 avec client_credentials."""
        data: dict[str, str] = {
            "grant_type": "client_credentials",
            "client_id": self._config.pa_client_id,
            "client_secret": self._config.pa_client_secret,
        }
        if self._config.pa_oauth_scope:
            data["scope"] = self._config.pa_oauth_scope

        async with httpx.AsyncClient(timeout=self._config.http_timeout) as client:
            response = await client.post(self._config.pa_token_url, data=data)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Échec obtention token OAuth2 : %s %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise

        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise ValueError(
                f"Réponse token OAuth2 invalide — access_token absent : {payload}"
            )

        expires_in = int(payload.get("expires_in", 3600))
        self._cache.set(access_token, expires_in)
        return access_token

    def invalidate_token(self) -> None:
        """Invalide le token en cache (à appeler après un 401)."""
        self._cache.invalidate()


# ---------------------------------------------------------------------------
# Singleton d'application — instancié une seule fois au démarrage du serveur
# ---------------------------------------------------------------------------

_config: Optional[PAConfig] = None
_oauth_client: Optional[OAuthClient] = None


def get_config() -> PAConfig:
    """Retourne la configuration singleton (chargée depuis .env)."""
    global _config
    if _config is None:
        _config = PAConfig()  # type: ignore[call-arg]
        if _config.debug:
            logging.basicConfig(level=logging.DEBUG)
    return _config


def get_oauth_client() -> OAuthClient:
    """Retourne le client OAuth2 singleton."""
    global _oauth_client
    if _oauth_client is None:
        _oauth_client = OAuthClient(get_config())
    return _oauth_client
