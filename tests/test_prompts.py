import pytest
from reviewer.prompts import build_prompts


def test_build_prompts_with_custom_rules():
    # 1. Arrange (Set up your fake data)
    diff = "+ print('hello world')"
    title = "Add greeting function"
    desc = "Adds a simple print statement to the main loop."
    custom_rules = "1. Strict Rule: All print statements must be logged instead."

    # 2. Act (Run your function)
    system_prompt, user_prompt = build_prompts(diff, title, desc, custom_rules)

    # 3. Assert (Verify the output)
    assert "Strict Rule: All print statements must be logged" in user_prompt
    assert "Add greeting function" in user_prompt
    assert "🔴 Critical Issues" in system_prompt


def test_build_prompts_without_custom_rules():
    system_prompt, user_prompt = build_prompts("+ int x = 1;", "Title", "Desc", "")

    assert "**Specific Project Rules:**" not in user_prompt
    assert "int x = 1;" in user_prompt


def test_build_prompts_truncates_massive_diffs():
    # Create a fake diff that is 60,000 characters long
    massive_diff = "a" * 60000

    system_prompt, user_prompt = build_prompts(massive_diff, "Title", "Desc", "")

    # Verify the safety truncation worked
    assert len(user_prompt) < 60000
    assert "... [truncated for token limits]" in user_prompt
