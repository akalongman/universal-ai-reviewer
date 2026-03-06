import pytest
from unittest.mock import patch, MagicMock
from reviewer.llm_providers import AnthropicReviewer


@patch('reviewer.llm_providers.Anthropic')
def test_anthropic_reviewer_stream_parsing(mock_anthropic_class):
    # 1. Setup the Mock (Fake the Anthropic Stream response)
    mock_client = MagicMock()
    mock_stream_context = MagicMock()

    # Simulate Claude streaming back text chunk by chunk
    mock_stream_context.text_stream = ["🔴 Critical Issues:\n", "- You have an N+1 query here."]

    # Wire the mock so the 'with client.messages.stream(...)' block uses our fake stream
    mock_client.messages.stream.return_value.__enter__.return_value = mock_stream_context
    mock_anthropic_class.return_value = mock_client

    # 2. Act
    reviewer = AnthropicReviewer()
    result = reviewer.review(
        system_prompt="Sys Rules",
        user_prompt="User Diff",
        api_key="fake_key_123"
    )

    # 3. Assert
    assert "🔴 Critical Issues:" in result
    assert "- You have an N+1 query here." in result

    # Verify the Anthropic client was called with the correct model
    mock_client.messages.stream.assert_called_once()
    call_kwargs = mock_client.messages.stream.call_args.kwargs
    assert call_kwargs['model'] == "claude-3-5-sonnet-latest"
