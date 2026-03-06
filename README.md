# 🤖 Universal AI Code Reviewer

A platform-agnostic, multi-model AI code review assistant that plugs directly into your CI/CD pipelines. It automatically analyzes Pull/Merge Requests for bugs, security vulnerabilities, performance bottlenecks, and code quality issues.

Built with extensibility in mind, this tool uses the Strategy pattern to seamlessly support multiple version control systems (GitHub, GitLab) and leading AI models (Anthropic's Claude, Google's Gemini).

## ✨ Key Features

* **Platform Agnostic:** Runs natively on GitHub Actions, GitLab CI, and can easily be extended to Bitbucket or Jenkins.
* **Multi-Model Support:** Switch between Claude (`claude-3-5-sonnet-latest`) and Gemini (`gemini-2.5-pro` / `gemini-1.5-pro-latest`) with a single environment variable.
* **Context-Aware:** Reads the PR/MR Title, Description, and actual code diffs to understand the *why* behind the changes.
* **Gatekeeper Mode:** Automatically fails the pipeline and blocks the merge if "🔴 Critical Issues" are detected.
* **Clean UI Feedback:** Posts a real-time "⏳ Thinking..." indicator, and hides nitpicks inside collapsible Markdown blocks so your PR timeline stays clean.
* **Custom Project Rules:** Enforce framework-specific standards (e.g., React hooks, Laravel Eloquent rules) via a simple `.ai-rules.md` file.

---

## 🚀 Quick Start

You don't need to install or host anything to use this tool. Just add the corresponding pipeline snippet to your project.

### Option A: GitHub Actions
Create a file at `.github/workflows/ai-review.yml` in your repository:

```yaml
name: AI Code Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0 
          
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Generate Diff
        run: git diff origin/${{ github.base_ref }}...HEAD > mr_diff.txt
        
      - name: Clone Universal AI Reviewer
        run: git clone -q https://github.com/akalongman/universal-ai-reviewer.git _shared_tools
        
      - name: Install Dependencies
        run: pip install -q -r _shared_tools/requirements.txt
        
      - name: Run Review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          # AI_PROVIDER: gemini  <-- Uncomment to use Gemini instead
        run: python _shared_tools/reviewer/main.py
```

### Option B: GitLab CI/CD
Add this job to your `.gitlab-ci.yml` file:

```yaml
ai_code_review:
  stage: review
  rules:
    - if: $CI_PIPELINE_SOURCE == 'merge_request_event'
  before_script:
    - if [ ! -d ".venv" ]; then python3 -m venv .venv; fi
    - source .venv/bin/activate
  script:
    - git fetch origin $CI_MERGE_REQUEST_TARGET_BRANCH_NAME
    - git diff origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME...HEAD > mr_diff.txt
    
    # Fetch the open-source reviewer directly from GitHub
    - git clone -q https://github.com/your-username/universal-ai-reviewer.git _shared_tools
    - pip install -q -r _shared_tools/requirements.txt
    - python _shared_tools/reviewer/main.py
```
*(Ensure `GITLAB_TOKEN` and your chosen AI API key are set in your GitLab CI/CD Variables).*

---

## ⚙️ Configuration Variables

The script automatically detects whether it is running in GitHub or GitLab. You only need to provide the necessary API keys as environment variables:

| Variable | Required? | Description |
| :--- | :--- | :--- |
| `AI_PROVIDER` | Optional | Set to `gemini` to use Google's models. Defaults to `anthropic`. |
| `ANTHROPIC_API_KEY` | Conditional | Required if using the default Anthropic provider. |
| `GEMINI_API_KEY` | Conditional | Required if `AI_PROVIDER` is set to `gemini`. |
| `GITHUB_TOKEN` | Conditional | Required for GitHub Actions (Auto-provided by `secrets.GITHUB_TOKEN`). |
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
The AI will automatically inject these rules into its system prompt during the review.

---

## 🤝 Contributing

We welcome contributions! Because this tool uses a modular Factory architecture, it is incredibly easy to add support for new platforms or LLMs.

1. **New AI Models:** Add a new class to `reviewer/llm_providers.py` implementing the `AIProvider` interface.
2. **New CI/CD Platforms:** Add a new class to `reviewer/vcs_providers.py` implementing the `VCSProvider` interface (e.g., `BitbucketProvider`).

To run the test suite locally:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -v
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
