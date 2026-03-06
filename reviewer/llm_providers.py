from abc import ABC, abstractmethod
from anthropic import Anthropic

# Import the new Google GenAI SDK
from google import genai
from google.genai import types


class AIProvider(ABC):
    @abstractmethod
    def review(self, system_prompt, user_prompt, api_key):
        pass


class AnthropicReviewer(AIProvider):
    def review(self, system_prompt, user_prompt, api_key):
        client = Anthropic(api_key=api_key)
        review_text = ""
        with client.messages.stream(
                model="claude-3-5-sonnet-latest",
                max_tokens=8192,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
        ) as stream:
            for text in stream.text_stream:
                review_text += text
        return review_text


class GeminiReviewer(AIProvider):
    def review(self, system_prompt, user_prompt, api_key):
        # Initialize the new Client
        client = genai.Client(api_key=api_key)

        # System instructions are now passed via a Config object
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
        )

        review_text = ""
        # Using the generate_content_stream method
        response = client.models.generate_content_stream(
            model='gemini-2.5-pro',
            contents=user_prompt,
            config=config
        )
        for chunk in response:
            if chunk.text:
                review_text += chunk.text
        return review_text


def get_provider(provider_name):
    if provider_name == "gemini":
        return GeminiReviewer()
    return AnthropicReviewer()
