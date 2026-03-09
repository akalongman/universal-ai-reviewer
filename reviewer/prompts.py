import os
import sys
import textwrap
import re
import fnmatch


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

            # Extract filename from 'diff --git a/path/to/file.txt b/path/to/file.txt'
            match = re.match(r'^diff --git a/(.*?) b/(.*?)$', line.strip())
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


def get_code_diff(file_path="mr_diff.txt"):
    try:
        with open(file_path, "r") as file:
            diff = file.read()
    except FileNotFoundError:
        print(f"No diff file found at {file_path}.")
        sys.exit(1)

    # Apply Smart Filtering
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


def build_prompts(diff, mr_title, mr_description, custom_rules):
    MAX_DIFF_SIZE = 50000
    if len(diff) > MAX_DIFF_SIZE:
        diff = diff[:MAX_DIFF_SIZE] + "\n\n... [truncated for token limits]"

    rules_injection = f"\n**Specific Project Rules:**\n{custom_rules}\n" if custom_rules else ""

    system_context = textwrap.dedent("""
        You are an expert, rigorous Principal Software Engineer.
        Review the Merge Request for bugs, security, and performance.

        Guidelines:
        1. Categorize feedback into: 🔴 Critical Issues, 🟡 Suggestions, and 🟢 Nitpicks/Praise.
        2. CLEANLINESS RULE: You MUST wrap all "🟢 Nitpicks/Praise" inside a Markdown collapsible block:
           <details><summary><b>🟢 Nitpicks & Praise</b></summary>
           (Your nitpicks here)
           </details>
        3. IMPORTANT: Do not complain about missing imports or variables if they might be defined elsewhere in the file (you only see a diff).
        4. Provide code fixes using GitLab's suggestion syntax: ```suggestion ... ``` when possible.
        5. Provide strictly Markdown. No greetings or preambles.
        6. If flawless, reply: "### \nLooks good to me! 🚀 No issues found."
    """).strip()

    user_prompt = textwrap.dedent(f"""
        Context regarding these changes:
        **MR Title:** {mr_title}
        **MR Description:** {mr_description}
        {rules_injection}
        Please review the following code changes:
        ```diff
        {diff}
        ```
    """).strip()

    return system_context, user_prompt
