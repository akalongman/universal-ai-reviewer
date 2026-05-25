from abc import ABC, abstractmethod
from anthropic import Anthropic
from google import genai
from google.genai import types
from openai import OpenAI

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
        # Using the generate_content_stream method
        response = client.models.generate_content_stream(
            model=config.model_name,
            contents=user_prompt,
            config=gemini_config
        )
        for chunk in response:
            if chunk.text:
                review_text += chunk.text
        return review_text


class OpenAIReviewer(AIProvider):
    def review(self, system_prompt, user_prompt, api_key, config):
        client = OpenAI(api_key=api_key)
        review_text = ""

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
            # Safely extract the chunk content (Delta might be empty for first/last chunks)
            if chunk.choices and chunk.choices[0].delta.content:
                review_text += chunk.choices[0].delta.content

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
