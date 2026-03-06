# 🤖 Universal AI Code Reviewer

A platform-agnostic, multi-model AI code review assistant that plugs directly into your CI/CD pipelines. It automatically analyzes Pull/Merge Requests for bugs, security vulnerabilities, performance bottlenecks, and code quality issues.

Built with extensibility in mind, this tool uses the Strategy pattern to seamlessly support multiple version control systems (GitHub, GitLab) and leading AI models (Anthropic's Claude, Google's Gemini).

---

## ✨ Key Features

* **Multi-VCS Support:** Native integration with **GitHub Actions** and **GitLab CI**.
* **Multi-Model Support:** Choose between **Claude 3.5 Sonnet** (Anthropic) or **Gemini 2.5 Pro** (Google).
* **Strategy Pattern Architecture:** Clean, modular Python codebase that is easy to extend.
* **Gatekeeper Mode:** Automatically blocks merges if `🔴 Critical Issues` are detected.
* **Collapsible Feedback:** Keeps the UI clean by hiding nitpicks inside `<details>` blocks.
* **Custom Project Context:** Define project-specific rules via `.ai-rules.md`.

---

## 🚀 Quick Start

You don't need to install or host anything to use this tool. Just add the corresponding pipeline snippet to your project.

### Option A: GitHub Actions (Recommended)
You can use this tool as a native GitHub Action. No setup required. Add the following step to your `.github/workflows/ai-review.yml`:

```yaml
- name: AI Code Review
  uses: akalongman/universal-ai-reviewer@main
  with:
    ai_provider: 'anthropic' # or 'gemini'
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    # gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
```

### Option B: GitLab CI/CD
GitLab users can include this template directly from GitHub. No local files needed. Add this to your `.gitlab-ci.yml`:

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

The script automatically detects whether it is running in GitHub or GitLab. You only need to provide the necessary API keys as environment variables:

| Variable | Required? | Description |
| :--- | :--- | :--- |
| `AI_PROVIDER` | Optional | `anthropic` (default) or `gemini`. |
| `ANTHROPIC_API_KEY` | Conditional | Required if using the default Anthropic provider. |
| `GEMINI_API_KEY` | Conditional | Required if `AI_PROVIDER` is set to `gemini`. |
| `GITHUB_TOKEN` | Auto | Automatically handled by GitHub Actions. |
| `GITLAB_TOKEN` | Conditional | Required for GitLab. Must be a PAT with `api` scope and Developer role. |

---

## 🧠 Customizing AI Rules (`.ai-rules.md`)

You can instruct the AI to enforce specific coding standards for your repository. Drop an `.ai-rules.md` file in the root of your project:

```markdown
# My Project Guidelines
1. Keep controllers thin; use Service classes for business logic.
2. Never return raw models; use API Resources.
3. Aggressively flag N+1 query problems in database calls.
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
   export AI_PROVIDER="anthropic"
   python reviewer/main.py
   ```

---

## 🤝 Contributing

We welcome contributions! Because this tool uses a modular Factory architecture, it is incredibly easy to add support for new platforms or LLMs.

1. **New AI Models:** Add a new class to `reviewer/llm_providers.py` implementing the `AIProvider` interface.
2. **New CI/CD Platforms:** Add a new class to `reviewer/vcs_providers.py` implementing the `VCSProvider` interface (e.g., `BitbucketProvider`).

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
