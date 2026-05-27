import pytest
from unittest.mock import patch, MagicMock
from reviewer.llm_providers import (
    AnthropicReviewer,
    GeminiReviewer,
    OpenAIReviewer,
    TruncatedResponseError,
    get_provider,
)


def test_get_provider_returns_correct_class_for_each_known_name():
    assert isinstance(get_provider("anthropic"), AnthropicReviewer)
    assert isinstance(get_provider("gemini"), GeminiReviewer)
    assert isinstance(get_provider("openai"), OpenAIReviewer)


def test_get_provider_raises_for_unknown_name():
    """Defense in depth: even if Config validation is bypassed (in tests or
    future refactors), the factory itself rejects unknown providers instead
    of silently returning an AnthropicReviewer that fails with a misleading
    SDK error downstream."""
    with pytest.raises(ValueError) as exc_info:
        get_provider("ollama")
    assert "ollama" in str(exc_info.value)
    assert "anthropic" in str(exc_info.value)
    assert "gemini" in str(exc_info.value)
    assert "openai" in str(exc_info.value)

@patch('reviewer.llm_providers.Anthropic')
def test_anthropic_reviewer_stream_parsing(mock_anthropic_class):
    # 1. Setup the Mock
    mock_client = MagicMock()
    mock_stream_context = MagicMock()
    mock_stream_context.text_stream = ["🔴 Critical Issues:\n", "- You have an N+1 query here."]
    mock_client.messages.stream.return_value.__enter__.return_value = mock_stream_context
    mock_anthropic_class.return_value = mock_client

    # Create a fake config object to pass into the review method
    mock_config = MagicMock()
    mock_config.model_name = "claude-sonnet-4-6"
    mock_config.max_tokens = 4096
    mock_config.temperature = 0.2

    # 2. Act
    reviewer = AnthropicReviewer()
    result = reviewer.review(
        system_prompt="Sys Rules",
        user_prompt="User Diff",
        api_key="fake_key_123",
        config=mock_config  # <-- Pass the mock config here
    )

    # 3. Assert
    assert "🔴 Critical Issues:" in result
    assert "- You have an N+1 query here." in result

    # Verify the Anthropic client was called with the correct dynamic model
    mock_client.messages.stream.assert_called_once()
    call_kwargs = mock_client.messages.stream.call_args.kwargs
    assert call_kwargs['model'] == "claude-sonnet-4-6" # <-- Assert the new model name


@patch('reviewer.llm_providers.genai.Client')
def test_gemini_reviewer_stream_parsing(mock_genai_client_class):
    # 1. Setup the Mock (Fake the Gemini Stream response)
    mock_client_instance = MagicMock()
    mock_genai_client_class.return_value = mock_client_instance

    # Create fake chunks that mimic Google's GenerateContentResponse structure
    chunk1 = MagicMock()
    chunk1.text = "🔴 Critical Issues:\n"
    chunk2 = MagicMock()
    chunk2.text = "- You have an N+1 query here."

    # Wire the mock so 'client.models.generate_content_stream' returns our fake chunks
    mock_client_instance.models.generate_content_stream.return_value = [chunk1, chunk2]

    # Create a fake config object
    mock_config = MagicMock()
    mock_config.model_name = "gemini-2.0-flash"
    mock_config.max_tokens = 4096
    mock_config.temperature = 0.2

    # 2. Act
    reviewer = GeminiReviewer()
    result = reviewer.review(
        system_prompt="Sys Rules",
        user_prompt="User Diff",
        api_key="fake_gemini_key",
        config=mock_config
    )

    # 3. Assert
    assert "🔴 Critical Issues:" in result
    assert "- You have an N+1 query here." in result

    # Verify the Gemini client was called correctly
    mock_client_instance.models.generate_content_stream.assert_called_once()

    # Check that dynamic config variables were properly passed to the API
    call_kwargs = mock_client_instance.models.generate_content_stream.call_args.kwargs
    assert call_kwargs['model'] == "gemini-2.0-flash"
    assert call_kwargs['config'].temperature == 0.2
    assert call_kwargs['config'].max_output_tokens == 4096


@patch('reviewer.llm_providers.OpenAI')
def test_openai_reviewer_stream_parsing(mock_openai_class):
    # 1. Setup the Mock (Fake the OpenAI Stream response)
    mock_client_instance = MagicMock()
    mock_openai_class.return_value = mock_client_instance

    # Create fake chunks that mimic OpenAI's ChatCompletionChunk structure
    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.content = "🔴 Critical Issues:\n"

    chunk2 = MagicMock()
    chunk2.choices = [MagicMock()]
    chunk2.choices[0].delta.content = "- You have an N+1 query here."

    # Wire the mock so 'client.chat.completions.create' returns an iterable of our chunks
    mock_client_instance.chat.completions.create.return_value = [chunk1, chunk2]

    # Create a fake config object
    mock_config = MagicMock()
    mock_config.model_name = "gpt-4o"
    mock_config.max_tokens = 8192
    mock_config.temperature = 0.2

    # 2. Act
    reviewer = OpenAIReviewer()
    result = reviewer.review(
        system_prompt="Sys Rules",
        user_prompt="User Diff",
        api_key="fake_openai_key",
        config=mock_config
    )

    # 3. Assert
    assert "🔴 Critical Issues:" in result
    assert "- You have an N+1 query here." in result

    # Verify the OpenAI client was called correctly
    mock_client_instance.chat.completions.create.assert_called_once()

    # Check that dynamic config variables were properly passed to the API
    call_kwargs = mock_client_instance.chat.completions.create.call_args.kwargs
    assert call_kwargs['model'] == "gpt-4o"
    assert call_kwargs['temperature'] == 0.2
    assert call_kwargs['max_completion_tokens'] == 8192
    assert 'max_tokens' not in call_kwargs
    assert call_kwargs['stream'] is True


# ---------- truncation detection ----------
#
# Each provider has its own sentinel for "stream ended because max_tokens was
# hit." A truncated stream may include the directive but a half-written issues
# section, which is unsafe to post. These tests guard the cross-SDK detection.


@patch('reviewer.llm_providers.OpenAI')
def test_openai_reviewer_raises_on_length_finish_reason(mock_openai_class):
    """OpenAI signals max_tokens via finish_reason='length' on the final chunk."""
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.content = "partial review..."
    chunk1.choices[0].finish_reason = None

    final_chunk = MagicMock()
    final_chunk.choices = [MagicMock()]
    final_chunk.choices[0].delta.content = None
    final_chunk.choices[0].finish_reason = "length"

    mock_client.chat.completions.create.return_value = [chunk1, final_chunk]

    config = MagicMock(model_name="gpt-4o", max_tokens=8192, temperature=0.2)
    with pytest.raises(TruncatedResponseError) as exc_info:
        OpenAIReviewer().review("sys", "user", "fake-key", config)
    assert "AI_MAX_TOKENS" in str(exc_info.value)


@patch('reviewer.llm_providers.Anthropic')
def test_anthropic_reviewer_raises_on_max_tokens_stop_reason(mock_anthropic_class):
    """Anthropic signals max_tokens via stop_reason='max_tokens' on the final message."""
    mock_client = MagicMock()
    mock_stream_context = MagicMock()
    mock_stream_context.text_stream = ["partial review..."]
    final_message = MagicMock()
    final_message.stop_reason = "max_tokens"
    mock_stream_context.get_final_message.return_value = final_message
    mock_client.messages.stream.return_value.__enter__.return_value = mock_stream_context
    mock_anthropic_class.return_value = mock_client

    config = MagicMock(model_name="claude-sonnet-4-6", max_tokens=4096, temperature=0.2)
    with pytest.raises(TruncatedResponseError) as exc_info:
        AnthropicReviewer().review("sys", "user", "fake-key", config)
    assert "AI_MAX_TOKENS" in str(exc_info.value)


@patch('reviewer.llm_providers.genai.Client')
def test_gemini_reviewer_raises_on_max_tokens_finish_reason(mock_genai_client_class):
    """Gemini signals max_tokens via candidates[0].finish_reason being the
    FinishReason.MAX_TOKENS enum (whose .name is 'MAX_TOKENS')."""
    mock_client_instance = MagicMock()
    mock_genai_client_class.return_value = mock_client_instance

    fake_enum = MagicMock()
    fake_enum.name = "MAX_TOKENS"

    chunk = MagicMock()
    chunk.text = "partial review..."
    chunk.candidates = [MagicMock(finish_reason=fake_enum)]

    mock_client_instance.models.generate_content_stream.return_value = [chunk]

    config = MagicMock(model_name="gemini-2.5-pro", max_tokens=4096, temperature=0.2)
    with pytest.raises(TruncatedResponseError) as exc_info:
        GeminiReviewer().review("sys", "user", "fake-key", config)
    assert "AI_MAX_TOKENS" in str(exc_info.value)
