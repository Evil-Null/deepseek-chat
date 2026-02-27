import json
import logging
from typing import Generator

import httpx
from httpx_sse import connect_sse
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import AppConfig, MODELS
from .models import APIResponse, UsageInfo, CostInfo

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base API error."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class RateLimitError(APIError):
    pass


class AuthenticationError(APIError):
    pass


class DeepSeekClient:
    def __init__(self, config: AppConfig):
        self.config = config
        self.client = httpx.Client(
            base_url=config.api_base_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(connect=10, read=120, write=10, pool=10),
        )

    def _build_payload(self, messages: list[dict], model: str, **overrides) -> dict:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }
        # deepseek-reasoner doesn't support temperature/top_p
        if model != "deepseek-reasoner":
            payload["temperature"] = self.config.temperature
            payload["top_p"] = self.config.top_p
        payload.update(overrides)
        return payload

    def stream_chat(
        self, messages: list[dict], model: str, **overrides
    ) -> Generator[str | dict | APIResponse, None, None]:
        """
        Stream a chat completion (OpenAI-compatible delta streaming).
        Yields:
          - dict with "reasoning" key: reasoning_content delta tokens
          - str: content delta tokens (for display)
          - APIResponse: final response object (last yield, after stream ends)
        """
        payload = self._build_payload(messages, model, **overrides)
        full_content = ""
        full_reasoning = ""
        final_usage = {}

        try:
            with connect_sse(
                self.client, "POST", "/chat/completions", json=payload
            ) as event_source:
                # Check HTTP status before iterating
                if event_source.response.status_code == 401:
                    raise AuthenticationError("Invalid API key", 401)
                if event_source.response.status_code == 429:
                    raise RateLimitError("Rate limited. Wait and retry.", 429)
                if event_source.response.status_code >= 400:
                    raise APIError(
                        f"API error {event_source.response.status_code}",
                        event_source.response.status_code,
                    )

                for sse in event_source.iter_sse():
                    if sse.data == "[DONE]":
                        break

                    try:
                        chunk = json.loads(sse.data)
                    except json.JSONDecodeError:
                        continue

                    # Capture usage from the final chunk
                    if "usage" in chunk:
                        final_usage = chunk["usage"]

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})

                    # Reasoning content (R1 model)
                    reasoning_delta = delta.get("reasoning_content", "")
                    if reasoning_delta:
                        full_reasoning += reasoning_delta
                        yield {"reasoning": reasoning_delta}

                    # Regular content
                    content_delta = delta.get("content", "")
                    if content_delta:
                        full_content += content_delta
                        yield content_delta

        except (AuthenticationError, RateLimitError, APIError):
            raise
        except httpx.TimeoutException:
            raise APIError("Request timed out. The server took too long to respond.")
        except httpx.TransportError as e:
            raise APIError(f"Network error: {e}")

        # Build final response
        yield self._build_final_response(full_content, full_reasoning, final_usage, model)

    def _build_final_response(
        self, content: str, reasoning: str, usage_raw: dict, model: str
    ) -> APIResponse:
        """Build final APIResponse with usage and cost calculation."""
        usage = UsageInfo(
            prompt_tokens=usage_raw.get("prompt_tokens", 0),
            completion_tokens=usage_raw.get("completion_tokens", 0),
            total_tokens=usage_raw.get("total_tokens", 0),
            prompt_cache_hit_tokens=usage_raw.get("prompt_cache_hit_tokens", 0),
            prompt_cache_miss_tokens=usage_raw.get("prompt_cache_miss_tokens", 0),
        )

        # Calculate cost
        model_info = MODELS.get(model, MODELS["deepseek-chat"])
        input_cost = (usage.prompt_tokens / 1_000_000) * model_info["input_cost"]
        output_cost = (usage.completion_tokens / 1_000_000) * model_info["output_cost"]

        cost = CostInfo(
            input_tokens_cost=input_cost,
            output_tokens_cost=output_cost,
            total_cost=input_cost + output_cost,
        )

        return APIResponse(
            content=content,
            reasoning_content=reasoning,
            usage=usage,
            cost=cost,
            model=model,
            finish_reason="stop",
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    def chat(self, messages: list[dict], model: str, **overrides) -> APIResponse:
        """Non-streaming fallback with retries."""
        payload = self._build_payload(messages, model, stream=False, **overrides)
        response = self.client.post("/chat/completions", json=payload)
        self._check_response(response)
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        reasoning = data["choices"][0]["message"].get("reasoning_content", "")
        usage_raw = data.get("usage", {})
        return self._build_final_response(content, reasoning, usage_raw, model)

    def _check_response(self, response: httpx.Response):
        if response.status_code == 401:
            raise AuthenticationError("Invalid API key", 401)
        if response.status_code == 429:
            raise RateLimitError("Rate limited. Wait and retry.", 429)
        if response.status_code >= 400:
            raise APIError(
                f"API error {response.status_code}: {response.text}",
                response.status_code,
            )

    def close(self):
        self.client.close()
