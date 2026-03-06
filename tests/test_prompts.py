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


def test_get_ignore_patterns_loads_defaults():
    patterns = get_ignore_patterns("non_existent_file.aiignore")
    assert "*.lock" in patterns
    assert "*.svg" in patterns
