from abc import ABC, abstractmethod
from anthropic import Anthropic

# Import the new Google GenAI SDK
from google import genai
from google.genai import types


class AIProvider(ABC):
    @abstractmethod
    def review(self, system_prompt, user_prompt, api_key, config):
        pass


class AnthropicReviewer(AIProvider):
    def review(self, system_prompt, user_prompt, api_key, config):
        client = Anthropic(api_key=api_key)
        review_text = ""
        with client.messages.stream(
                model=config.model_name,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
        ) as stream:
            for text in stream.text_stream:
                review_text += text
        return review_text


class GeminiReviewer(AIProvider):
    def review(self, system_prompt, user_prompt, api_key, config):
        # Initialize the new Client
        client = genai.Client(api_key=api_key)

        # System instructions are now passed via a Config object
        gemini_config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=config.max_tokens,
            temperature=config.temperature,
        )

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


def get_provider(provider_name):
    if provider_name == "gemini":
        return GeminiReviewer()
    return AnthropicReviewer()
