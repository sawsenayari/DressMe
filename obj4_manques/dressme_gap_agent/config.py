"""Environment-backed settings for the local 9Router-compatible agent."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
import os
from urllib.parse import urlparse


class ConfigurationError(ValueError):
    """Raised when required settings are missing or unsafe."""


def _is_loopback(hostname: str) -> bool:
    if hostname.lower() == "localhost":
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class AgentConfig:
    base_url: str = "http://127.0.0.1:20128/v1"
    api_key: str = ""
    model: str = ""
    compatibility_model: str = "groq/openai/gpt-oss-120b"
    vision_model: str = ""
    temperature: float = 0.2
    max_tokens: int = 600
    max_judge_tokens: int = 1600
    timeout_seconds: float = 30.0
    max_user_chars: int = 4000
    max_answer_chars: int = 3000
    allow_remote_router: bool = False
    max_retries: int = 1
    retry_backoff_seconds: float = 0.5
    compatibility_batch_delay_seconds: float = 0.0

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ConfigurationError("DRESSME_LLM_BASE_URL must be an http(s) URL.")
        if parsed.username or parsed.password:
            raise ConfigurationError("Do not put credentials in DRESSME_LLM_BASE_URL.")
        if not self.allow_remote_router and not _is_loopback(parsed.hostname):
            raise ConfigurationError(
                "The router must be local by default. For a trusted remote gateway, "
                "set DRESSME_ALLOW_REMOTE_ROUTER=true explicitly."
            )
        if not _is_loopback(parsed.hostname) and parsed.scheme != "https":
            raise ConfigurationError("Remote router connections must use HTTPS.")
        if not self.api_key.strip():
            raise ConfigurationError("Set DRESSME_LLM_API_KEY to your local 9Router API key.")
        if not self.model.strip():
            raise ConfigurationError("Set DRESSME_LLM_MODEL to the 9Router combo/model name.")
        if not 0 <= self.temperature <= 2:
            raise ConfigurationError("DRESSME_LLM_TEMPERATURE must be between 0 and 2.")
        if not 1 <= self.max_tokens <= 4096:
            raise ConfigurationError("DRESSME_LLM_MAX_TOKENS must be between 1 and 4096.")
        if not 100 <= self.max_judge_tokens <= 4096:
            raise ConfigurationError("DRESSME_LLM_JUDGE_MAX_TOKENS must be between 100 and 4096.")
        if not 1 <= self.timeout_seconds <= 180:
            raise ConfigurationError("DRESSME_LLM_TIMEOUT must be between 1 and 180 seconds.")
        if not 0 <= self.max_retries <= 2:
            raise ConfigurationError("DRESSME_LLM_MAX_RETRIES must be between 0 and 2.")
        if not 0 <= self.retry_backoff_seconds <= 5:
            raise ConfigurationError("DRESSME_LLM_RETRY_BACKOFF must be between 0 and 5 seconds.")
        if not 0 <= self.compatibility_batch_delay_seconds <= 60:
            raise ConfigurationError("DRESSME_LLM_BATCH_DELAY must be between 0 and 60 seconds.")

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Read already-loaded environment settings without printing secrets."""
        return cls(
            base_url=os.getenv("DRESSME_LLM_BASE_URL", "http://127.0.0.1:20128/v1").rstrip("/"),
            api_key=os.getenv("DRESSME_LLM_API_KEY", ""),
            model=os.getenv("DRESSME_LLM_MODEL", ""),
            compatibility_model=os.getenv(
                "DRESSME_LLM_COMPAT_MODEL", "groq/openai/gpt-oss-120b"
            ).strip(),
            vision_model=os.getenv("DRESSME_LLM_VISION_MODEL", "").strip(),
            temperature=float(os.getenv("DRESSME_LLM_TEMPERATURE", "0.2")),
            max_tokens=int(os.getenv("DRESSME_LLM_MAX_TOKENS", "600")),
            max_judge_tokens=int(os.getenv("DRESSME_LLM_JUDGE_MAX_TOKENS", "1600")),
            timeout_seconds=float(os.getenv("DRESSME_LLM_TIMEOUT", "30")),
            allow_remote_router=os.getenv("DRESSME_ALLOW_REMOTE_ROUTER", "false").lower()
            in {"1", "true", "yes"},
            max_retries=int(os.getenv("DRESSME_LLM_MAX_RETRIES", "1")),
            retry_backoff_seconds=float(os.getenv("DRESSME_LLM_RETRY_BACKOFF", "0.5")),
            compatibility_batch_delay_seconds=float(os.getenv("DRESSME_LLM_BATCH_DELAY", "0")),
        )
