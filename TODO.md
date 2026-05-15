# 📋 Universal AI Code Reviewer - Roadmap & TODOs

This document outlines planned features and improvements to make this tool a tier-1 open-source project.

## 🧠 Advanced AI Capabilities & UX

- [ ] **Post "Inline" Line-by-Line Code Comments**
  - **What:** Update the system prompt to output a JSON schema mapping issues to specific lines of code, then use the GitHub/GitLab APIs to post native review threads *directly on those lines* in the MR/PR.
  - **Why:** Provides a vastly superior User Experience (UX), matching how human developers conduct code reviews.
  - **Effort:** High (Requires complex API interactions and accurate line-number mapping from the diff).

- [x] **Full-File Context (Prevent Hallucinations)**
  - **What:** Opt in via `AI_FETCH_CHANGED_FULL=true`. Goes beyond the original scope: also fetches imported files (JS, TS, PHP in v1) via `AI_FETCH_RELATED_FILES=true` plus `AI_FETCH_RELATED_DEPTH=N` for traversal control. Tree-sitter based import extraction, `tsconfig.json` / `composer.json` aware path resolution, context window overflow fails loudly with an actionable message.
  - **Status:** Shipped. Canonical spec: `openspec/specs/context-fetching/spec.md`. Archived change: `openspec/changes/archive/2026-05-14-add-full-file-context/`.

- [ ] **Support Local / Private Models (Ollama)**
  - **What:** Add a `LocalProvider` that connects to a local instance like `localhost:11434` using the standard OpenAI SDK format.
  - **Why:** Allows enterprise teams with strict data privacy laws to run open-source models (like Llama-3 or DeepSeek-Coder) inside their secure networks for free.
  - **Effort:** Low.

## ⚡ Performance, Cost & DX

- [ ] **Local CLI Mode (Developer Experience)**
  - **What:** Support reading `git diff --staged` directly from the developer's local machine and outputting the review to the terminal using a rich text library.
  - **Why:** Allows developers to get instant AI feedback on uncommitted changes before pushing to CI/CD.
  - **Effort:** Medium.

- [ ] **Diff Hashing & Caching**
  - **What:** Hash the `mr_diff.txt` and store the AI's markdown response in the CI/CD cache using the hash as the key.
  - **Why:** Prevents wasting API tokens and saves time when developers click "Retry Pipeline" on flaky tests without actually changing the code.
  - **Effort:** Medium.
Upd
## 🛠️ Codebase Polish

- [ ] **Add Python Type Hints**
  - **What:** Update all method signatures and variables with strict Python type hints (e.g., `def review(self, system_prompt: str, ...) -> str:`).
  - **Why:** Improves codebase readability and developer experience for future open-source contributors.
  - **Effort:** Low.

- [ ] **Implement Linting, Formatting & Pre-commit Hooks**
  - **What:** Add `ruff` (fast Python linter/formatter) to the project, set up a `.pre-commit-config.yaml`, and enforce it via a GitHub Action.
  - **Why:** Ensures the code meets professional Python standards, completely eliminates formatting debates, and catches easy bugs.
  - **Effort:** Low.
