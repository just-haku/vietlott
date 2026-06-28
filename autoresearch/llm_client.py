"""
Multi-provider LLM client for the Auto-Research Engine.

Supports Google Gemini, Groq, DeepSeek, OpenAI, and Anthropic via HTTP APIs.
Uses requests.Session with connection pooling for efficient reuse across
the research loop. No heavy SDK dependencies.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider configuration registry
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, dict] = {
    'google': {
        'name': 'Google Gemini',
        'default_model': 'gemma-4-27b-it',
        'endpoint_template': 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        'env_key': 'GOOGLE_API_KEY',
        'auth_style': 'query_param',       # API key passed as ?key=...
    },
    'groq': {
        'name': 'Groq',
        'default_model': 'llama-3.3-70b-versatile',
        'endpoint': 'https://api.groq.com/openai/v1/chat/completions',
        'env_key': 'GROQ_API_KEY',
        'auth_style': 'bearer',
    },
    'deepseek': {
        'name': 'DeepSeek',
        'default_model': 'deepseek-chat',
        'endpoint': 'https://api.deepseek.com/v1/chat/completions',
        'env_key': 'DEEPSEEK_API_KEY',
        'auth_style': 'bearer',
    },
    'openai': {
        'name': 'OpenAI',
        'default_model': 'gpt-4o-mini',
        'endpoint': 'https://api.openai.com/v1/chat/completions',
        'env_key': 'OPENAI_API_KEY',
        'auth_style': 'bearer',
    },
    'anthropic': {
        'name': 'Anthropic',
        'default_model': 'claude-sonnet-4-20250514',
        'endpoint': 'https://api.anthropic.com/v1/messages',
        'env_key': 'ANTHROPIC_API_KEY',
        'auth_style': 'x-api-key',
    },
}


def _build_session(max_retries: int = 3, pool_connections: int = 4,
                   pool_maxsize: int = 8) -> requests.Session:
    """Create a requests.Session with connection pooling and retries."""
    session = requests.Session()
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=['POST'],
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
    )
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


def _find_config(config_path: Optional[str] = None) -> dict:
    """
    Load config.json from the project root or the provided path.

    Expected structure:
    {
        "google_api_key": "...",
        "groq_api_key": "...",
        "deepseek_api_key": "...",
        "openai_api_key": "...",
        "anthropic_api_key": "...",
        "default_provider": "google",
        "default_model": "gemma-4-27b-it"
    }
    """
    if config_path:
        p = Path(config_path)
    else:
        # Walk up from this file to find project root config.json
        p = Path(__file__).resolve().parent.parent / 'config.json'

    if p.exists():
        try:
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Failed to load config from %s: %s", p, e)

    return {}


class LLMClient:
    """
    Multi-provider LLM client with connection pooling.

    Supports Google Gemini, Groq, DeepSeek, OpenAI, and Anthropic.
    Configuration is loaded from config.json at project root, or from
    environment variables, or passed directly.

    Usage:
        client = LLMClient(provider='google')
        response = client.generate("What is 2+2?")
        print(response)
    """

    def __init__(
        self,
        provider: str = 'google',
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        config_path: Optional[str] = None,
    ):
        """
        Initialize the LLM client.

        Args:
            provider: One of 'google', 'groq', 'deepseek', 'openai', 'anthropic'.
            model: Model name override. If None, uses provider default.
            api_key: API key override. If None, loads from config/env.
            config_path: Path to config.json. If None, searches project root.
        """
        if provider not in PROVIDERS:
            raise ValueError(
                f"Unknown provider '{provider}'. "
                f"Available: {list(PROVIDERS.keys())}"
            )

        self._provider_name = provider
        self._provider = PROVIDERS[provider]
        self._config = _find_config(config_path)

        # Resolve model
        self._model = model or self._config.get(
            'default_model', self._provider['default_model']
        )

        # Resolve API key: explicit > config.json > env var
        self._api_key = api_key
        if not self._api_key:
            config_key = f"{provider}_api_key"
            self._api_key = self._config.get(config_key)
        if not self._api_key:
            self._api_key = os.environ.get(self._provider['env_key'], '')

        if not self._api_key:
            logger.warning(
                "No API key found for provider '%s'. "
                "Set %s env var or add to config.json.",
                provider, self._provider['env_key']
            )

        # Connection pool
        self._session = _build_session()

        logger.info(
            "LLMClient initialized: provider=%s, model=%s",
            provider, self._model
        )

    def generate(
        self,
        prompt: str,
        system_prompt: str = '',
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system-level instructions.
            temperature: Sampling temperature (0.0–2.0).
            max_tokens: Maximum tokens in the response.

        Returns:
            The generated text response.

        Raises:
            ConnectionError: If the API request fails after retries.
            ValueError: If the response cannot be parsed.
        """
        if self._provider_name == 'google':
            return self._generate_google(prompt, system_prompt, temperature, max_tokens)
        elif self._provider_name == 'anthropic':
            return self._generate_anthropic(prompt, system_prompt, temperature, max_tokens)
        else:
            return self._generate_openai_compat(prompt, system_prompt, temperature, max_tokens)

    def _generate_google(
        self, prompt: str, system_prompt: str,
        temperature: float, max_tokens: int,
    ) -> str:
        """Google Gemini API (non-OpenAI format)."""
        endpoint = self._provider['endpoint_template'].format(model=self._model)

        contents = []
        if system_prompt:
            contents.append({
                'role': 'user',
                'parts': [{'text': f"[System Instructions]\n{system_prompt}"}]
            })
            contents.append({
                'role': 'model',
                'parts': [{'text': 'Understood. I will follow these instructions.'}]
            })
        contents.append({
            'role': 'user',
            'parts': [{'text': prompt}]
        })

        payload = {
            'contents': contents,
            'generationConfig': {
                'temperature': temperature,
                'maxOutputTokens': max_tokens,
            },
        }

        response = self._session.post(
            endpoint,
            params={'key': self._api_key},
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()

        try:
            candidates = data['candidates']
            text = candidates[0]['content']['parts'][0]['text']
            return text
        except (KeyError, IndexError) as e:
            logger.error("Failed to parse Google response: %s", data)
            raise ValueError(f"Unexpected Google API response structure: {e}") from e

    def _generate_openai_compat(
        self, prompt: str, system_prompt: str,
        temperature: float, max_tokens: int,
    ) -> str:
        """OpenAI-compatible API (Groq, DeepSeek, OpenAI)."""
        endpoint = self._provider['endpoint']
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        payload = {
            'model': self._model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._api_key}',
        }

        response = self._session.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()

        try:
            return data['choices'][0]['message']['content']
        except (KeyError, IndexError) as e:
            logger.error("Failed to parse OpenAI-compat response: %s", data)
            raise ValueError(f"Unexpected API response structure: {e}") from e

    def _generate_anthropic(
        self, prompt: str, system_prompt: str,
        temperature: float, max_tokens: int,
    ) -> str:
        """Anthropic Messages API."""
        endpoint = self._provider['endpoint']

        payload: dict = {
            'model': self._model,
            'max_tokens': max_tokens,
            'temperature': temperature,
            'messages': [{'role': 'user', 'content': prompt}],
        }
        if system_prompt:
            payload['system'] = system_prompt

        headers = {
            'Content-Type': 'application/json',
            'x-api-key': self._api_key,
            'anthropic-version': '2023-06-01',
        }

        response = self._session.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()

        try:
            content_blocks = data['content']
            text_parts = [b['text'] for b in content_blocks if b['type'] == 'text']
            return ''.join(text_parts)
        except (KeyError, IndexError, TypeError) as e:
            logger.error("Failed to parse Anthropic response: %s", data)
            raise ValueError(f"Unexpected Anthropic API response structure: {e}") from e

    def get_config(self) -> dict:
        """
        Return current provider configuration.

        Returns:
            Dict with provider name, model, endpoint, and key status.
        """
        return {
            'provider': self._provider_name,
            'provider_name': self._provider['name'],
            'model': self._model,
            'has_api_key': bool(self._api_key),
            'auth_style': self._provider['auth_style'],
        }

    @staticmethod
    def list_providers() -> list[dict]:
        """
        List all supported providers and their default models.

        Returns:
            List of dicts with provider info.
        """
        return [
            {
                'id': pid,
                'name': info['name'],
                'default_model': info['default_model'],
                'env_key': info['env_key'],
            }
            for pid, info in PROVIDERS.items()
        ]

    def close(self) -> None:
        """Close the underlying connection pool."""
        self._session.close()

    def __enter__(self) -> 'LLMClient':
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"LLMClient(provider='{self._provider_name}', "
            f"model='{self._model}', "
            f"has_key={bool(self._api_key)})"
        )
