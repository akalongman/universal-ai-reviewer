import pytest
from reviewer.prompts import build_prompts
from reviewer.prompts import filter_diff, get_ignore_patterns


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


def test_filter_diff_removes_noisy_files():
    # Arrange: A fake diff containing both a legitimate Python file and a noisy lockfile
    raw_diff = """diff --git a/main.py b/main.py
index 83db48f..99a0932 100644
--- a/main.py
+++ b/main.py
@@ -1,2 +1,3 @@
 def hello():
-    print("world")
+    print("AI Reviewer")
diff --git a/package-lock.json b/package-lock.json
index 1234567..890abcd 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -100,2 +100,3 @@
     "lodash": "^4.17.21"
+    "axios": "^1.6.0"
"""

    # Act
    patterns = ["package-lock.json"]
    filtered = filter_diff(raw_diff, patterns)

    # Assert
    assert "main.py" in filtered
    assert "print(\"AI Reviewer\")" in filtered
    assert "package-lock.json" not in filtered
    assert "axios" not in filtered


def test_get_ignore_patterns_empty_by_default():
    # Act: Try to load a file that doesn't exist
    patterns = get_ignore_patterns("non_existent_file.aiignore")

    # Assert: It should return a completely empty list, not defaults
    assert patterns == []
    assert len(patterns) == 0


def test_build_prompts_with_fetched_files_emits_section():
    fetched = {"src/handler.js": "console.log('hi');"}
    system_prompt, user_prompt = build_prompts(
        "+ diff body", "Title", "Desc", "", fetched_files=fetched,
    )
    assert "**Full File Context:**" in user_prompt
    assert "**File: src/handler.js**" in user_prompt
    assert "console.log('hi');" in user_prompt
    full_idx = user_prompt.index("**Full File Context:**")
    diff_idx = user_prompt.index("```diff")
    assert full_idx < diff_idx
    assert "read only context" in system_prompt


def test_build_prompts_without_fetched_files_omits_section():
    system_prompt, user_prompt = build_prompts(
        "+ diff body", "Title", "Desc", "", fetched_files=None,
    )
    assert "**Full File Context:**" not in user_prompt
    assert "read only context" not in system_prompt


def test_build_prompts_with_empty_fetched_dict_omits_section():
    system_prompt, user_prompt = build_prompts(
        "+ diff body", "Title", "Desc", "", fetched_files={},
    )
    assert "**Full File Context:**" not in user_prompt


def test_build_prompts_preserves_category_header_contract_with_fetched_files():
    fetched = {"src/x.js": "// x"}
    system_prompt, _ = build_prompts(
        "+ diff", "Title", "Desc", "", fetched_files=fetched,
    )
    assert "🔴 Critical Issues" in system_prompt
    assert "🟡 Suggestions" not in system_prompt or "🟢 Nitpicks/Praise" in system_prompt
    assert "OMIT" in system_prompt or "completely omit" in system_prompt.lower()
