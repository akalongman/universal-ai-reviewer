# 📋 Universal AI Code Reviewer - Roadmap & TODOs

This document outlines planned features and improvements to make this tool a tier-1 open-source project.

## 🚀 High-Impact Features

- [x] **OpenAI (GPT-4o) Support**
  - **What:** Create an `OpenAIReviewer` class implementing the `AIProvider` interface.
  - **Why:** OpenAI is the industry standard for many enterprise teams. Supporting it expands the potential user base significantly.
  - **Effort:** Low (Leverages existing Strategy pattern).

- [ ] **Smart File Filtering (Ignore Noise)**
  - **What:** Add an `.aiignore` file support or hardcoded filters to exclude noisy files (e.g., `package-lock.json`, `yarn.lock`, `*.svg`, `dist/`, `build/`) from the `git diff`.
  - **Why:** Saves API costs, speeds up the review, and prevents the AI from hallucinating issues in auto-generated files.
  - **Effort:** Low to Medium (Modifying the `git diff` generation step).

## 🧠 Advanced AI Capabilities

- [ ] **Post "Inline" Code Comments**
  - **What:** Update the system prompt to output a JSON schema mapping issues to specific lines of code, then use the GitHub/GitLab APIs to post comments *directly on those lines* in the MR/PR.
  - **Why:** Provides a vastly superior User Experience (UX), matching how human developers conduct code reviews.
  - **Effort:** High (Requires complex API interactions and accurate line-number mapping from the diff).

- [ ] **Full-File Context (Prevent Hallucinations)**
  - **What:** For small diffs, fetch the *full contents* of the edited files via the VCS API and provide them as context to the AI alongside the diff.
  - **Why:** Drastically reduces "false positives" by allowing the AI to see how new code interacts with the rest of the file (e.g., seeing where a function is defined).
  - **Effort:** Medium.

- [ ] **Support Local / Private Models (Ollama)**
  - **What:** Add a `LocalProvider` that connects to a local instance like `localhost:11434` using the standard OpenAI SDK format.
  - **Why:** Allows enterprise teams with strict data privacy laws to run open-source models (like Llama-3 or DeepSeek-Coder) inside their secure networks for free.
  - **Effort:** Low.

## 🛠️ Codebase Polish

- [ ] **Add Python Type Hints**
  - **What:** Update all method signatures and variables with strict Python type hints (e.g., `def review(self, system_prompt: str, ...) -> str:`).
  - **Why:** Improves codebase readability and developer experience for future open-source contributors.

- [ ] **Implement Linting & Formatting**
  - **What:** Add `flake8` or `ruff` to the project and run it via a dedicated GitHub Action on Pull Requests to this repository.
  - **Why:** Ensures the code meets professional Python standards and catches easy bugs.
