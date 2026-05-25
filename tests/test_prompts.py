import pytest
from reviewer.prompts import build_prompts, MAX_DIFF_SIZE, critical_section_is_empty
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
    massive_diff = "a" * (MAX_DIFF_SIZE + 10000)

    system_prompt, user_prompt = build_prompts(massive_diff, "Title", "Desc", "")

    assert len(user_prompt) < len(massive_diff)
    assert "... [truncated for token limits]" in user_prompt


def test_build_prompts_truncation_logs_warning(capsys):
    build_prompts("a" * (MAX_DIFF_SIZE + 500), "Title", "Desc", "")
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "500" in captured.out


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


@pytest.mark.parametrize("review_text", [
    "### 🔴 Critical Issues\n\nNone.",
    "### 🔴 Critical Issues\n\n- None",
    "### 🔴 Critical Issues\n\n**None.**",
    "🔴 Critical Issues:\n- N/A",
    "## 🔴 Critical Issues\n\n*None identified*",
    "### 🔴 Critical Issues\n\n0 issues found.",
    "### 🔴 Critical Issues\n\n> No issues.\n\n### 🟡 Suggestions\n- Real suggestion",
    "### 🔴 Critical Issues\n",
    "### 🔴 Critical Issues\n\nNo critical issues found.",
    "### 🔴 Critical Issues\n\nNothing critical.",
    "### 🔴 Critical Issues\n\nNo blocking issues.",
    "### 🔴 Critical Issues\n\nNo major issues to report.",
    "### 🔴 Critical Issues\n\nNone of significance.",
])
def test_critical_section_is_empty_recognises_negations(review_text):
    assert critical_section_is_empty(review_text) is True


@pytest.mark.parametrize("review_text", [
    "### 🔴 Critical Issues\n\n- SQL injection in `update_user` (file.py:42)",
    "### 🔴 Critical Issues\n\n**Race condition** in the worker pool.",
    "🔴 Critical Issues\n1. Hardcoded credential\n2. Missing auth check",
])
def test_critical_section_is_empty_detects_real_issues(review_text):
    assert critical_section_is_empty(review_text) is False


@pytest.mark.parametrize("review_text", [
    # The "None, but..." pattern that previously slipped through and let real
    # findings ship past the gatekeeper. The closed-vocabulary check rejects
    # each of these because the body contains at least one token outside the
    # allow-list ("but", "however", "except", "minor", "hardcoded", "sql",
    # filenames, etc).
    "### 🔴 Critical Issues\n\nNone of significance, but watch the SQL injection at file.py:42",
    "### 🔴 Critical Issues\n\nNo blocking issues, however a race condition in the worker pool may be exploitable",
    "### 🔴 Critical Issues\n\nNo major problems found. Minor: hardcoded credential at config.py:18 (could be promoted to critical)",
    "### 🔴 Critical Issues\n\nNone, except SQL injection at users.py:42",
    "### 🔴 Critical Issues\n\nNo critical issues but the auth middleware bypasses CSRF protection",
])
def test_critical_section_is_empty_rejects_adversarial_hedges(review_text):
    """Regression guard for the closed-vocabulary check.

    A real finding mixed into a "None"-led section MUST fail the gatekeeper.
    The previous first-word-only check returned True for all of these and let
    the build pass with critical issues described in plain text.
    """
    assert critical_section_is_empty(review_text) is False


@pytest.mark.parametrize("review_text", [
    # Allow-list-only attack: the body uses ONLY tokens from _ALLOWED_EMPTY_TOKENS
    # but the second sentence is an affirmation, not a negation. The sentence-start
    # check is what catches these — closed vocabulary alone is not sufficient.
    "### 🔴 Critical Issues\n\nNone to report. Critical bugs found.",
    "### 🔴 Critical Issues\n\nNone of any significance. Critical bugs identified.",
    "### 🔴 Critical Issues\n\nNothing major. Critical issues found.",
    "### 🔴 Critical Issues\n\nNo issues of significance. Critical bugs detected.",
])
def test_critical_section_is_empty_rejects_allow_list_only_attack(review_text):
    """Regression guard for the sentence-start negation check.

    These inputs all use only allow-list vocabulary, so the closed-vocabulary
    check alone returns True. The second-sentence affirmation ("Critical bugs
    found.") must force the section to be treated as non-empty.

    This is the most subtle bypass class: a determined adversary or confused
    model can use legitimate-looking vocabulary while still describing real
    findings. The proper structural fix is a structured-output handshake;
    this test guards the heuristic stopgap.
    """
    assert critical_section_is_empty(review_text) is False


def test_critical_section_is_empty_without_header():
    assert critical_section_is_empty("### 🟡 Suggestions\n- Use a constant.") is False
