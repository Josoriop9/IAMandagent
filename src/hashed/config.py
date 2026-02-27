"""
Configuration management for the Hashed SDK.

This module handles SDK configuration with support for environment
variables and programmatic configuration.
"""

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

from hashed.exceptions import HashedConfigError

# Load environment variables from .env file
load_dotenv()

# Credentials file path
_CREDENTIALS_FILE = Path.home() / ".hashed" / "credentials.json"


def _load_credential(key: str) -> Optional[str]:
    """Load a value from ~/.hashed/credentials.json"""
    try:
        if _CREDENTIALS_FILE.exists():
            creds = json.loads(_CREDENTIALS_FILE.read_text())
            return creds.get(key)
    except Exception:
        pass
    return None


class HashedConfig(BaseModel):
    """
    Configuration model for the Hashed SDK.

    This class follows the Dependency Inversion Principle by providing
    a clear configuration interface that the SDK depends on.
    
    Reads from environment variables:
        API_KEY or HASHED_API_KEY: API key for authentication
        BACKEND_URL or HASHED_BACKEND_URL: Backend URL
    """

    # Backend Configuration
    # Priority: env vars > .env file > ~/.hashed/credentials.json
    api_key: Optional[str] = Field(
        default_factory=lambda: (
            os.getenv("API_KEY") or
            os.getenv("HASHED_API_KEY") or
            _load_credential("api_key") or
            None
        ),
        description="API key for backend authentication (X-API-KEY header)",
    )
    backend_url: Optional[str] = Field(
        default_factory=lambda: (
            os.getenv("BACKEND_URL") or
            os.getenv("HASHED_BACKEND_URL") or
            _load_credential("backend_url") or
            "https://iamandagent-production.up.railway.app"
        ),
        description="Backend Control Plane URL",
    )
    
    # Legacy API Configuration (deprecated, use backend_url)
    api_url: str = Field(
        default="https://api.hashed.example.com",
        description="Base URL for the API (legacy)",
    )
    
    # Policy Sync Configuration
    sync_interval: int = Field(
        default=300,
        ge=60,
        description="Seconds between policy syncs from backend",
    )
    enable_auto_sync: bool = Field(
        default=True,
        description="Enable automatic policy synchronization",
    )
    
    # Ledger Configuration
    ledger_endpoint: str = Field(
        default="/v1/logs/batch",
        description="Endpoint path for log ingestion",
    )
    
    # HTTP Configuration
    timeout: float = Field(
        default=30.0,
        gt=0,
        description="Request timeout in seconds",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum number of retries for failed requests",
    )
    verify_ssl: bool = Field(
        default=True,
        description="Whether to verify SSL certificates",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    class Config:
        """Pydantic configuration."""

        frozen = True  # Make the config immutable
        validate_assignment = True

    @field_validator("api_url")
    @classmethod
    def validate_api_url(cls, v: str) -> str:
        """Validate that the API URL is properly formatted."""
        if not v:
            raise HashedConfigError("API URL cannot be empty")
        if not v.startswith(("http://", "https://")):
            raise HashedConfigError(
                "API URL must start with http:// or https://"
            )
        return v.rstrip("/")

    @classmethod
    def from_env(cls) -> "HashedConfig":
        """
        Create configuration from environment variables.

        Environment variables:
            HASHED_API_KEY: API key for authentication
            HASHED_API_URL: Base URL for the API
            HASHED_TIMEOUT: Request timeout in seconds
            HASHED_MAX_RETRIES: Maximum number of retries
            HASHED_VERIFY_SSL: Whether to verify SSL certificates
            HASHED_DEBUG: Enable debug mode

        Returns:
            HashedConfig: Configuration instance

        Raises:
            HashedConfigError: If configuration is invalid
        """
        try:
            return cls(
                api_key=os.getenv("HASHED_API_KEY"),
                api_url=os.getenv(
                    "HASHED_API_URL", "https://api.hashed.example.com"
                ),
                timeout=float(os.getenv("HASHED_TIMEOUT", "30.0")),
                max_retries=int(os.getenv("HASHED_MAX_RETRIES", "3")),
                verify_ssl=os.getenv("HASHED_VERIFY_SSL", "true").lower() == "true",
                debug=os.getenv("HASHED_DEBUG", "false").lower() == "true",
            )
        except Exception as e:
            raise HashedConfigError(
                f"Failed to load configuration from environment: {e}"
            ) from e

    def with_overrides(self, **kwargs: any) -> "HashedConfig":
        """
        Create a new config with specific values overridden.

        Args:
            **kwargs: Configuration values to override

        Returns:
            HashedConfig: New configuration instance with overrides
        """
        config_dict = self.model_dump()
        config_dict.update(kwargs)
        return HashedConfig(**config_dict)
