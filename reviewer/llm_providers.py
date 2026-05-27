from abc import ABC, abstractmethod
from anthropic import Anthropic
from google import genai
from google.genai import types
from openai import OpenAI


class TruncatedResponseError(RuntimeError):
    """The model's response stream ended because the output token budget was
    exhausted. The partial response is unsafe to post as a review because the
    gatekeeper directive may be missing or the issues section incomplete."""


def _is_max_tokens_finish(value) -> bool:
    """Defensive equality: match against the canonical max-tokens sentinels for
    each SDK while staying inert when fed a MagicMock or other untyped value
    (so test fixtures that don't set finish_reason at all keep passing).

    OpenAI streams emit `"length"` on the final chunk when max_tokens is hit.
    Anthropic emits `"max_tokens"` as the final message's `stop_reason`.
    Google genai emits a `FinishReason.MAX_TOKENS` enum whose `.name` is the
    string `"MAX_TOKENS"`. Comparing against all three covers the cross-SDK
    truth set without importing each provider's enum module.
    """
    if value is None:
        return False
    candidate = getattr(value, "name", value)
    if not isinstance(candidate, str):
        return False
    return candidate in ("length", "max_tokens", "MAX_TOKENS")


class AIProvider(ABC):
    @abstractmethod
    def review(self, system_prompt, user_prompt, api_key, config):
        pass


class AnthropicReviewer(AIProvider):
    def review(self, system_prompt, user_prompt, api_key, config):
        client = Anthropic(api_key=api_key)
        kwargs = {
            "model": config.model_name,
            "max_tokens": config.max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if config.temperature is not None:
            kwargs["temperature"] = config.temperature

        review_text = ""
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                review_text += text
            stop_reason = None
            get_final = getattr(stream, "get_final_message", None)
            if callable(get_final):
                try:
                    final_message = get_final()
                except Exception:
                    final_message = None
                if final_message is not None:
                    stop_reason = getattr(final_message, "stop_reason", None)
        if _is_max_tokens_finish(stop_reason):
            raise TruncatedResponseError(
                f"Anthropic stream terminated with stop_reason={stop_reason!r}; "
                "the response is truncated. Increase AI_MAX_TOKENS or reduce the diff scope."
            )
        return review_text


class GeminiReviewer(AIProvider):
    def review(self, system_prompt, user_prompt, api_key, config):
        # Initialize the new Client
        client = genai.Client(api_key=api_key)

        config_kwargs = {
            "system_instruction": system_prompt,
            "max_output_tokens": config.max_tokens,
        }
        if config.temperature is not None:
            config_kwargs["temperature"] = config.temperature

        gemini_config = types.GenerateContentConfig(**config_kwargs)

        review_text = ""
        last_finish_reason = None
        response = client.models.generate_content_stream(
            model=config.model_name,
            contents=user_prompt,
            config=gemini_config
        )
        for chunk in response:
            if chunk.text:
                review_text += chunk.text
            candidates = getattr(chunk, "candidates", None) or []
            if candidates:
                reason = getattr(candidates[0], "finish_reason", None)
                if reason is not None:
                    last_finish_reason = reason

        if _is_max_tokens_finish(last_finish_reason):
            raise TruncatedResponseError(
                f"Gemini stream terminated with finish_reason={last_finish_reason!r}; "
                "the response is truncated. Increase AI_MAX_TOKENS or reduce the diff scope."
            )
        return review_text


class OpenAIReviewer(AIProvider):
    def review(self, system_prompt, user_prompt, api_key, config):
        client = OpenAI(api_key=api_key)
        review_text = ""
        last_finish_reason = None

        kwargs = {
            "model": config.model_name,
            "max_completion_tokens": config.max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": True,
        }
        if config.temperature is not None:
            kwargs["temperature"] = config.temperature

        response = client.chat.completions.create(**kwargs)

        for chunk in response:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.delta.content:
                review_text += choice.delta.content
            reason = getattr(choice, "finish_reason", None)
            if reason is not None:
                last_finish_reason = reason

        if _is_max_tokens_finish(last_finish_reason):
            raise TruncatedResponseError(
                f"OpenAI stream terminated with finish_reason={last_finish_reason!r}; "
                "the response is truncated. Increase AI_MAX_TOKENS or reduce the diff scope."
            )
        return review_text


def get_provider(provider_name):
    if provider_name == "anthropic":
        return AnthropicReviewer()
    if provider_name == "gemini":
        return GeminiReviewer()
    if provider_name == "openai":
        return OpenAIReviewer()
    raise ValueError(
        f"Unsupported AI_PROVIDER: {provider_name!r}. "
        "Expected one of: anthropic, gemini, openai."
    )
