import pytest
from unittest.mock import patch, MagicMock
from reviewer.llm_providers import AnthropicReviewer
from reviewer.llm_providers import GeminiReviewer

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
