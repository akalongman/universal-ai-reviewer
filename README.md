# 🤖 Universal AI Code Reviewer

A platform-agnostic, multi-model AI code review assistant that plugs directly into your CI/CD pipelines. It automatically analyzes Pull/Merge Requests for bugs, security vulnerabilities, performance bottlenecks, and code quality issues.

Built with extensibility in mind, this tool uses the Strategy pattern to seamlessly support multiple version control systems (GitHub, GitLab) and leading AI models (Anthropic's Claude, Google's Gemini, and OpenAI's GPT).

---

## ✨ Key Features

* **Multi-VCS Support:** Native integration with **GitHub Actions** and **GitLab CI**.
* **Multi-Model Support:** Choose between **Claude 3.5 Sonnet** (Anthropic), **Gemini 2.0 Flash/Pro** (Google), or **GPT-4o** (OpenAI).
* **Smart File Filtering:** Automatically ignores noisy files (like `package-lock.json`, `dist/`, `*.svg`) to save tokens and prevent hallucinated issues. Fully customizable via an `.aiignore` file.
* **Highly Configurable:** Fine-tune the review by choosing specific models, setting token limits, and adjusting the AI temperature.
* **Strategy Pattern Architecture:** Clean, modular Python codebase that is easy to extend.
* **Gatekeeper Mode:** Automatically blocks merges if `🔴 Critical Issues` are detected.
* **Collapsible Feedback:** Keeps the UI clean by hiding nitpicks inside `<details>` blocks.
* **Custom Project Context:** Define project-specific rules via `.ai-rules.md`.

---

## 🚀 Quick Start

You don't need to install or host anything to use this tool. Just add the corresponding pipeline snippet to your project.

### Option A: GitHub Actions (Recommended)
You can use this tool as a native GitHub Action. Ensure you set `fetch-depth: 0` to allow the tool to calculate the diff. Add the following to your `.github/workflows/ai-review.yml`:

```yaml
- name: AI Code Review
  uses: akalongman/universal-ai-reviewer@main
  with:
    ai_provider: 'openai' # or 'anthropic' / 'gemini'
    openai_api_key: ${{ secrets.OPENAI_API_KEY }}
    # anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    # gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
  env:
    # Optional Tuning
    AI_MODEL: 'gpt-4o' 
    AI_TEMPERATURE: '0.2'
```

### Option B: GitLab CI/CD
GitLab users can include this template directly from GitHub. The template automatically handles the `GIT_DEPTH: 0` requirement. Add this to your `.gitlab-ci.yml`:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/akalongman/universal-ai-reviewer/main/gitlab-template.yml'

# Ensure you have a 'review' stage defined
stages:
  - build
  - test
  - review
```

---

## ⚙️ Configuration Variables

The script automatically detects whether it is running in GitHub or GitLab. You can tune the behavior using the following environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `AI_PROVIDER` | `anthropic` | Set to `openai` or `gemini` to use other models. |
| `AI_MODEL` | Provider Dependent | Defaults to `claude-3-5-sonnet-latest`, `gemini-2.0-flash`, or `gpt-4o`. |
| `AI_MAX_TOKENS` | `8192` | The maximum length of the AI response. |
| `AI_TEMPERATURE` | `0.2` | Controls randomness (0.0 is strict, 1.0 is creative). |
| `ANTHROPIC_API_KEY` | - | Required if using the Anthropic provider. |
| `GEMINI_API_KEY` | - | Required if `AI_PROVIDER` is set to `gemini`. |
| `OPENAI_API_KEY` | - | Required if `AI_PROVIDER` is set to `openai`. |
| `GITLAB_TOKEN` | - | Required for GitLab (PAT with `api` scope). |
| `GITHUB_TOKEN` | Auto | Automatically handled by GitHub Actions. |

---

## 🧠 Customizing AI Rules & Filtering

### Project Guidelines (`.ai-rules.md`)
You can instruct the AI to enforce specific coding standards for your repository. Drop an `.ai-rules.md` file in the root of your project:

```markdown
# My Project Guidelines
1. Keep controllers thin; use Service classes for business logic.
2. Never return raw models; use API Resources.
3. Aggressively flag N+1 query problems in database calls.
```

### Ignore Noisy Files (`.aiignore`)
By default, the AI will review **all** files in the Pull/Merge Request. To save tokens and prevent the AI from reviewing auto-generated files (like lockfiles or compiled assets), create an `.aiignore` file in the root of your repository:

```text
# .aiignore example
*.lock
package-lock.json
public/build/*
dist/*
*.svg
```

---

## 🛠️ Local Development & Testing

This project uses `pytest` for local validation without making real API calls.

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Test Suite**:
   ```bash
   python -m pytest tests/ -v
   ```

3. **Manual Run**:
   ```bash
   export VCS_PROVIDER="github" # or "gitlab"
   export AI_PROVIDER="openai"
   python reviewer/main.py
   ```

---

## 🤝 Contributing

We welcome contributions! Because this tool uses a modular Factory architecture, it is incredibly easy to add support for new platforms or LLMs.

1. **New AI Models:** Add a new class to `reviewer/llm_providers.py` implementing the `AIProvider` interface.
2. **New CI/CD Platforms:** Add a new class to `reviewer/vcs_providers.py` implementing the `VCSProvider` interface.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
