import os
import sys
import textwrap
import re
import fnmatch
from datetime import datetime


MAX_DIFF_SIZE = 50000

_NEGATION_WORDS = {"none", "no", "0", "n/a", "na", "nothing"}

# A "truly empty" critical section must consist ONLY of tokens from this set.
# The vocabulary is intentionally narrow: adversarial hedges like
# "None of significance, but SQL injection at file.py:42" contain at least one
# token outside this set (here: "but", "watch", "sql", "injection"), which
# forces the gatekeeper to escalate. Extend this set only when a real model
# output legitimately needs a word that is not yet here. Each addition is a
# small attack-surface increase that should be reviewed deliberately.
_ALLOWED_EMPTY_TOKENS = {
    "none", "no", "0", "n/a", "na", "nothing",
    "issues", "critical", "problems", "concerns", "bugs",
    "found", "identified", "detected",
    "of", "any",
    "major", "blocking", "significant", "significance",
    "to", "report", "flag",
}

_MARKDOWN_NOISE_RE = re.compile(r"[\s\-\*>_`:.()\[\]!]+")


class DirectiveParseError(ValueError):
    """The AI response contained an ai-review directive that could not be parsed.

    Raised when an ai-review directive is present at the start of the response
    but is malformed (missing required keys, non-integer values, negative
    counts) or appears more than once. The gatekeeper treats this as
    fail-closed: the model attempted to signal severity but failed, which is
    a stronger smell than the directive being absent altogether.
    """


_REQUIRED_DIRECTIVE_KEYS = ("critical", "suggestions", "nitpicks")
_DIRECTIVE_PREFIX_RE = re.compile(r"\A\s*<!--\s*(.*?)\s*-->", re.DOTALL)
_ANY_DIRECTIVE_COMMENT_RE = re.compile(r"<!--\s*(.*?)\s*-->", re.DOTALL)


def parse_severity_directive(review_text):
    """Parse the leading ai-review directive from an AI response.

    Returns:
        A dict with int values for at least the three required keys
        (`critical`, `suggestions`, `nitpicks`) when a valid directive is
        present at the start of the response.

        None when the response does not start with an HTML comment, or starts
        with an HTML comment that is not an ai-review directive. This is the
        signal for the gatekeeper to fall back to legacy prose parsing.

    Raises:
        DirectiveParseError when a directive is present but malformed, or
        when more than one ai-review directive appears anywhere in the body.
    """
    if not isinstance(review_text, str):
        return None
    first_match = _DIRECTIVE_PREFIX_RE.match(review_text)
    if not first_match:
        return None
    content = first_match.group(1).strip()
    if not content.lower().startswith("ai-review:"):
        return None

    # Detect a second ai-review directive anywhere in the response. Two
    # directives signal model confusion (or attempted manipulation); the
    # fail-closed posture treats this as suspicious rather than picking one.
    for extra in _ANY_DIRECTIVE_COMMENT_RE.finditer(review_text, first_match.end()):
        extra_content = extra.group(1).strip().lower()
        if extra_content.startswith("ai-review:"):
            raise DirectiveParseError(
                "Response contained more than one ai-review directive; only one is permitted."
            )

    payload = content[len("ai-review:"):].strip()
    if not payload:
        raise DirectiveParseError("Empty ai-review directive payload; expected key=value pairs.")

    parsed = {}
    for pair in payload.split(";"):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise DirectiveParseError(
                f"Malformed ai-review directive segment {pair!r}; expected key=value."
            )
        key, value = pair.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        try:
            count = int(value)
        except ValueError:
            raise DirectiveParseError(
                f"Malformed ai-review directive value: {key}={value!r}. "
                "Expected a non-negative integer."
            )
        if count < 0:
            raise DirectiveParseError(
                f"Negative count in ai-review directive: {key}={count}."
            )
        parsed[key] = count

    missing = [k for k in _REQUIRED_DIRECTIVE_KEYS if k not in parsed]
    if missing:
        raise DirectiveParseError(
            f"ai-review directive missing required key(s): {', '.join(missing)}. "
            f"Got keys: {sorted(parsed)}."
        )
    return parsed


def gatekeeper_exit_code(review_text):
    """Decide the CI exit code from the AI response.

    Returns 0 (pass) or 1 (fail). Pure function: only side effect is print
    statements that surface in CI logs. Called by `main.py` which translates
    the return value into `sys.exit`.

    Decision precedence:
    1. Malformed directive → 1 (fail-closed; model attempted to signal but failed)
    2. Valid directive with `critical > 0` → 1
    3. Valid directive with `critical == 0` → 0 (warns if body has 🔴 header)
    4. No directive, prose says non-empty critical section → 1 (with DEPRECATION log)
    5. No directive, prose says empty critical section → 0 (with DEPRECATION log)
    """
    try:
        directive = parse_severity_directive(review_text)
    except DirectiveParseError as exc:
        print(
            f"ERROR: AI response contained a malformed severity directive: {exc} "
            "Marking job as FAILED (fail-closed)."
        )
        return 1

    if directive is not None:
        critical = directive["critical"]
        suggestions = directive["suggestions"]
        nitpicks = directive["nitpicks"]
        print(
            f"Severity directive: critical={critical}, "
            f"suggestions={suggestions}, nitpicks={nitpicks}"
        )
        if critical == 0 and "🔴 Critical Issues" in review_text:
            print(
                "WARNING: directive says critical=0 but body contains a "
                "'🔴 Critical Issues' header. Trusting the directive."
            )
        if critical > 0:
            print(f"[!] {critical} CRITICAL ISSUE(S) DETECTED. Marking job as FAILED.")
            return 1
        print("[✓] No critical issues found. Marking job as PASSED.")
        return 0

    print(
        "DEPRECATION: AI response did not include a severity directive; "
        "falling back to prose parsing. Upgrade the system prompt (>=1.2.0) "
        "to emit '<!-- ai-review: critical=N; suggestions=N; nitpicks=N -->' "
        "as the first line. Prose parsing will be removed in 2.0."
    )
    if "🔴 Critical Issues" in review_text and not critical_section_is_empty(review_text):
        print("[!] CRITICAL ISSUES DETECTED. Marking job as FAILED.")
        return 1
    print("[✓] No critical issues found. Marking job as PASSED.")
    return 0


def critical_section_is_empty(review_text: str) -> bool:
    """Return True when the AI wrote a 🔴 Critical Issues header but its body is purely negation.

    The system prompt instructs the model to OMIT the header entirely when there
    are no critical issues, but models drift. This backstop tolerates common
    markdown phrasings (bullets, bold, blockquotes, exclamation marks) around
    explicit negations like "None", "No critical issues found", or "N/A".

    Two checks layered on the stripped body:

    1. Closed-vocabulary: every token must be in `_ALLOWED_EMPTY_TOKENS`. Catches
       adversarial hedges like "None of significance, but SQL injection at
       file.py:42" because words like "but", "watch", "sql" are out of vocabulary.

    2. Sentence-start negation: every sentence in the body (split on `.!?`) must
       begin with a word from `_NEGATION_WORDS`. Catches the
       allow-list-only attack like "None to report. Critical bugs found." where
       the adversarial payload lives in a second sentence that starts with
       "Critical" rather than a negation.

    KNOWN LIMITATION: these are heuristics, not proofs. A sufficiently clever
    model output that uses only allow-listed vocabulary and starts every
    sentence with a negation word could still slip through. The structurally
    correct fix is to switch to structured output (the model emits a parseable
    counter that the gatekeeper reads, instead of inspecting prose). See the
    pending `gatekeeper-structured-output` OpenSpec change for that work.
    """
    header = re.search(r"🔴 Critical Issues[^\n]*\n", review_text)
    if not header:
        return False
    body_start = header.end()
    next_section = re.search(r"\n#{1,6}\s|\n🟡|\n🟢", review_text[body_start:])
    body_end = body_start + next_section.start() if next_section else len(review_text)
    body = review_text[body_start:body_end]
    stripped = _MARKDOWN_NOISE_RE.sub(" ", body).strip().lower()
    if not stripped:
        return True
    tokens = stripped.split()
    if tokens[0] not in _NEGATION_WORDS:
        return False
    if not all(token in _ALLOWED_EMPTY_TOKENS for token in tokens):
        return False
    for sentence in re.split(r"[.!?]", body.lower()):
        sentence_stripped = _MARKDOWN_NOISE_RE.sub(" ", sentence).strip()
        if not sentence_stripped:
            continue
        if sentence_stripped.split()[0] not in _NEGATION_WORDS:
            return False
    return True

def get_ignore_patterns(file_path=".aiignore"):
    """Returns a list of patterns to ignore from a local .aiignore file."""
    patterns = []

    if os.path.exists(file_path):
        print(f"Found {file_path}! Loading custom ignore patterns...")
        try:
            with open(file_path, "r") as f:
                # Add non-empty lines that aren't comments
                custom_patterns = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                patterns.extend(custom_patterns)
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")

    if patterns:
        print(f"Active Ignore Patterns: {', '.join(patterns)}")
    else:
        print("No active ignore patterns (.aiignore not found or empty). Reviewing all changed files.")

    return patterns

def filter_diff(diff_text, ignore_patterns):
    """Parses a unified git diff and removes file chunks that match the ignore patterns."""
    filtered_diff = []
    current_file_diff = []
    keep_file = True

    for line in diff_text.splitlines(True):
        if line.startswith('diff --git '):
            # Process the previous file chunk before starting a new one
            if keep_file and current_file_diff:
                filtered_diff.extend(current_file_diff)

            # Reset state for the new file
            current_file_diff = [line]
            keep_file = True

            # Extract filename from 'diff --git a/path b/path'. The b/ path
            # is the post-rename identity of the file; matching .aiignore
            # against it is intentional, so that a real source file renamed
            # into an ignored name (or vice versa) is matched on its new
            # name. The optional quote handles git's quoted-path format for
            # filenames containing spaces ('"a/path with space" "b/...").
            match = re.match(r'^diff --git "?a/(.+?)"? "?b/(.+?)"?$', line.strip())
            if match:
                filename = match.group(2)
                # Check if the filename matches any of our ignore patterns
                for pattern in ignore_patterns:
                    # Match exact pattern or pattern within directories (e.g., */*.svg)
                    if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(filename, f"*/{pattern}"):
                        print(f"  -> Ignoring noisy file: {filename} (matched '{pattern}')")
                        keep_file = False
                        break
        else:
            current_file_diff.append(line)

    # Append the very last file chunk
    if keep_file and current_file_diff:
        filtered_diff.extend(current_file_diff)

    return "".join(filtered_diff)


def get_code_diff(file_path="mr_diff.txt", ignore_patterns=None):
    try:
        with open(file_path, "r") as file:
            diff = file.read()
    except FileNotFoundError:
        print(f"No diff file found at {file_path}.")
        sys.exit(1)

    if ignore_patterns is None:
        ignore_patterns = get_ignore_patterns()
    diff = filter_diff(diff, ignore_patterns)

    if not diff.strip():
        print("No code changes to review after filtering. Exiting gracefully.")
        sys.exit(0)
    return diff


def get_custom_rules(file_path=".ai-rules.md"):
    if os.path.exists(file_path):
        print(f"Found {file_path}! Injecting custom project rules...")
        try:
            with open(file_path, "r") as rules_file:
                return rules_file.read().strip()
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return ""
    return os.environ.get("AI_PROJECT_CONTEXT", "").strip()


def build_prompts(diff, mr_title, mr_description, custom_rules, fetched_files=None):
    if len(diff) > MAX_DIFF_SIZE:
        dropped = len(diff) - MAX_DIFF_SIZE
        print(
            f"WARNING: diff exceeded {MAX_DIFF_SIZE} chars; {dropped} chars truncated. "
            f"The model will review only the first {MAX_DIFF_SIZE} chars and may miss "
            f"issues in the dropped section."
        )
        diff = diff[:MAX_DIFF_SIZE] + "\n\n... [truncated for token limits]"

    rules_injection = f"\n**Specific Project Rules:**\n{custom_rules}\n" if custom_rules else ""

    full_file_section = ""
    full_file_note = ""
    if fetched_files:
        blocks = []
        for path, content in fetched_files.items():
            blocks.append(f"**File: {path}**\n```\n{content}\n```")
        full_file_section = "\n**Full File Context:**\n" + "\n\n".join(blocks) + "\n"
        full_file_note = (
            "\n        7. The user message includes a **Full File Context:** section with the head version of "
            "changed files and their direct imports. Treat that content as read only context for understanding "
            "the diff; do not invent issues in code that is not part of the diff itself."
        )

    # Get today's actual date
    current_date = datetime.now().strftime("%B %d, %Y")

    system_context = textwrap.dedent(f"""
        You are an expert, rigorous Principal Software Engineer.
        Review the Merge Request for bugs, security, and performance.

        CRITICAL CONTEXT: Today's date is {current_date}. Do not flag timestamps, migration files, or copyright notices as "future dates" if they match the current year.

        CI GATEKEEPER DIRECTIVE (MOST IMPORTANT, READ THIS FIRST):
        Every response MUST begin with this exact line, with accurate counts:
        <!-- ai-review: critical=N; suggestions=N; nitpicks=N -->
        - All three keys MUST be present and MUST be non-negative integers.
        - This directive is the ONLY signal the CI gatekeeper reads to decide pass/fail.
        - The markdown body below the directive is for human reviewers; the gatekeeper does not parse it.
        - If you omit, duplicate, or malform this directive, the CI job fails.

        Guidelines for the body that follows the directive:
        1. Categorize feedback into: 🔴 Critical Issues, 🟡 Suggestions, 🟢 Nitpicks/Praise.
           These headers exist for human readability; the gatekeeper does not read them.
           Match the section counts to the directive's `critical`, `suggestions`, `nitpicks` values respectively.
        2. CLEANLINESS RULE: You MUST wrap all "🟢 Nitpicks/Praise" inside a Markdown collapsible block:
           <details><summary><b>🟢 Nitpicks & Praise</b></summary>
           (Your nitpicks here)
           </details>
        3. IMPORTANT: Do not complain about missing imports or variables if they might be defined elsewhere in the file (you only see a diff).
        4. Provide code fixes using GitLab/GitHub suggestion syntax: ```suggestion ... ``` when possible.
        5. Provide strictly Markdown. No greetings or preambles between the directive and the first section.
        6. If flawless, reply exactly:
           <!-- ai-review: critical=0; suggestions=0; nitpicks=0 -->
           ### Looks good to me! 🚀 No issues found.{full_file_note}
    """).strip()

    user_prompt = textwrap.dedent(f"""
        Context regarding these changes:
        **MR Title:** {mr_title}
        **MR Description:** {mr_description}
        {rules_injection}{full_file_section}
        Please review the following code changes:
        ```diff
        {diff}
        ```
    """).strip()

    return system_context, user_prompt
