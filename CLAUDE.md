# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A CI/CD bot that posts an AI generated code review comment on a Pull Request (GitHub) or Merge Request (GitLab). It is consumed in two ways:

1. As a GitHub composite action (`action.yaml`) referenced via `uses: akalongman/universal-ai-reviewer@<ref>`.
2. As a GitLab CI template (`gitlab-template.yml`) included from a downstream `.gitlab-ci.yml`. Note that the GitLab template re-clones this repo into `_shared_tools/` at job time, so changes only take effect once they land on the ref the consumer pins.

There is no library API, no `setup.py`, no `pyproject.toml`. The entrypoint is `reviewer/main.py`.

## Spec-driven development

This project uses OpenSpec for non-trivial changes. This file (CLAUDE.md) is the project constitution, the source of truth for tech stack, architecture, and conventions. The capability map and OpenSpec-native conventions live in `openspec/config.yaml`.

Workflow: `/opsx:propose` → `/opsx:apply` → `/opsx:archive`. For exploratory thinking without committing to a change, use `/opsx:explore`.

When inline rule detail in this file grows past about five lines on a topic, that is the signal to extract it into a born-populated capability spec under `openspec/specs/<capability>/spec.md` via the propose / apply / archive cycle, and replace the inline block with a row in a capability-spec table. Until then, the inline sections below stay as the source of truth.

### Capability specs (Progressive Disclosure)

For canonical detail, read the cited capability spec under `openspec/specs/<name>/spec.md`. Rules below are summaries; the spec is the source of truth.

| Topic | Spec | Rule summary |
|---|---|---|
| Full file context fetching | `context-fetching` | Opt in via `AI_FETCH_CHANGED_FULL` / `AI_FETCH_RELATED_FILES` / `AI_FETCH_RELATED_DEPTH`. Tree-sitter import extraction for JS, TS, and PHP only; other languages still get full content of changed files but skip related resolution. Repo-root `tsconfig.json` and `composer.json` only. Overflow fails loudly, no silent truncation. |

## Commands

All commands run from the repo root.

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full test suite
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_prompts.py -v

# Run a single test by name
python -m pytest tests/test_providers.py::test_anthropic_reviewer_stream_parsing -v

# Manual run (requires mr_diff.txt and the relevant API keys + VCS env vars)
export VCS_PROVIDER=github   # or "gitlab", used only when neither GITHUB_ACTIONS nor GITLAB_CI is set
export AI_PROVIDER=openai
python reviewer/main.py
```

The tests use `pytest-mock` and `unittest.mock` to stub the SDKs. No network calls are made during testing.

## Import layout gotcha

`reviewer/main.py` uses bare sibling imports (`from config import Config`, `from prompts import ...`). These resolve only because Python adds the script's directory to `sys.path` when you invoke `python reviewer/main.py`. The tests, by contrast, use package style imports (`from reviewer.prompts import ...`), so pytest must be run from the repo root.

Do not "fix" one half to match the other without changing the matching half: both CI runners (`action.yaml`, `gitlab-template.yml`) invoke `main.py` as a script, and both test files import `reviewer.x`.

## Pipeline (reviewer/main.py)

The entrypoint runs a fixed seven step sequence and uses process exit codes as its only output channel to CI:

1. Build `Config` (auto-detects VCS via `GITLAB_CI` or `GITHUB_ACTIONS`, falls back to the `VCS_PROVIDER` env var).
2. Instantiate the VCS client (factory `get_vcs_provider`) and fetch MR/PR title and description.
3. Read `mr_diff.txt` from the working directory. The CI runners are responsible for generating this with `git diff origin/<base>...HEAD > mr_diff.txt`.
4. Post a `⏳ Thinking...` placeholder comment so reviewers see live feedback.
5. Build system + user prompts (`build_prompts`), select the AI provider (factory `get_provider`), and call `.review(...)`.
6. Edit the placeholder comment with the final markdown.
7. Gatekeeper: delegates to `prompts.gatekeeper_exit_code(review_text)`. Reads a structured `<!-- ai-review: critical=N; suggestions=N; nitpicks=N -->` directive at the first non-whitespace line of the response. Exits 1 when `critical > 0` or when the directive is malformed (fail-closed). When the directive is absent, falls back to legacy prose parsing (`critical_section_is_empty`) with a `DEPRECATION` log line. This exit code is what fails the CI job, so downstream consumers control hard vs soft failure via `continue-on-error` (GitHub) or `allow_failure` (GitLab), not via any flag inside this repo.

If the AI call fails, the placeholder is edited with the error message and the job exits 1.

## Architecture

Two parallel Strategy + Factory pairs, one for each axis of pluggability:

| Concern | Abstract base | Implementations | Factory |
|---|---|---|---|
| VCS hosting | `VCSProvider` (`reviewer/vcs_providers.py`) | `GitLabProvider`, `GitHubProvider` | `get_vcs_provider(config)` |
| AI provider | `AIProvider` (`reviewer/llm_providers.py`) | `AnthropicReviewer`, `GeminiReviewer`, `OpenAIReviewer` | `get_provider(name)` |

To add a new VCS or LLM, subclass the relevant ABC, add the implementation to the factory, and follow the existing mock pattern in `tests/test_providers.py`. All three current AI providers stream tokens and concatenate them into a single string. Keep that contract: `main.py` treats `review_text` as a complete markdown blob.

`Config` (`reviewer/config.py`) is the single source of all environment variable wiring. It validates per detected platform: if `vcs_type == "gitlab"` it requires `GITLAB_TOKEN`, `CI_PROJECT_ID`, `CI_MERGE_REQUEST_IID`; if `"github"` it requires `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_EVENT_PATH`. Add new env vars here, not scattered in modules.

Default models (when `AI_MODEL` is unset) are hardcoded in `Config.__init__`: `claude-sonnet-4-6`, `gemini-2.5-pro`, `gpt-4o`. The README table is out of sync (it lists older defaults); update the README when changing them.

## Prompt and diff handling (reviewer/prompts.py)

Three behaviours that are easy to break and worth understanding before editing:

* **Diff truncation.** The diff is hard truncated at 50000 characters before being sent to the model (`MAX_DIFF_SIZE` in `build_prompts`). Test `test_build_prompts_truncates_massive_diffs` enforces this.
* **`.aiignore` filtering.** `filter_diff` parses the unified diff, splits it on `diff --git` headers, and drops any file whose `b/` path matches a pattern from `.aiignore` via `fnmatch`. Patterns are matched both directly and as `*/{pattern}` so that bare names like `package-lock.json` match nested copies. There are no default ignore patterns: an absent or empty `.aiignore` means "review everything".
* **`.ai-rules.md` injection.** If present in the repo being reviewed, its contents are injected verbatim into the user prompt under a `**Specific Project Rules:**` heading. Falls back to the `AI_PROJECT_CONTEXT` env var if the file is missing.

The system prompt instructs the model to begin every response with a `<!-- ai-review: critical=N; suggestions=N; nitpicks=N -->` directive at the first non-whitespace line. That directive is the only signal the gatekeeper reads. The category headers (`🔴 Critical Issues` / `🟡 Suggestions` / `🟢 Nitpicks/Praise`) remain in the prompt for human readability and are wrapped in `<details>` blocks for nitpicks, but the gatekeeper no longer reads them. Changes to the directive format must be made in both `prompts.build_prompts` (the instruction) and `prompts.parse_severity_directive` (the parser); changes to category headers can now be made in isolation. The dual-read window means `critical_section_is_empty` (the prose-parsing fallback) is still load-bearing for responses missing the directive; do not remove it before 2.0.

The current date is rendered into the system prompt via `datetime.now()` so the model does not flag current year timestamps as "future dates" (a real false positive class that was hitting migrations and copyright notices).

## When editing CI integration files

* `action.yaml`: the `gemini_api_key` and `openai_api_key` inputs are referenced in the `env:` block but only `anthropic_api_key` and `gemini_api_key` are declared under `inputs:`. If you touch this file, declare every input that the env block references.
* `gitlab-template.yml`: pins `python3 -m venv .venv` and re-clones this repo from `main` into `_shared_tools/`. Consumers typically pin a tag (e.g. `1.0.0`) when including the remote template, so version compatibility between the included template and the cloned code matters. Do not move shared logic between the two without considering this split.

## Repository hygiene

* `mr_diff.txt` is a runtime artifact, gitignored, and expected at the working directory root by `get_code_diff`.
* No linter, formatter, or pre-commit hooks are currently configured. `.editorconfig` is the only style enforcement (4 space indent, LF, UTF-8, 200 char max line length). The `TODO.md` lists ruff + pre-commit as planned work; do not assume they exist.