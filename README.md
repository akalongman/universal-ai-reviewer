# 🤖 Universal AI Code Reviewer

A platform-agnostic, multi-model AI code review assistant that plugs directly into your CI/CD pipelines. It automatically analyzes Pull/Merge Requests for bugs, security vulnerabilities, performance bottlenecks, and code quality issues.

Built with extensibility in mind, this tool uses the Strategy pattern to seamlessly support multiple version control systems (GitHub, GitLab) and leading AI models (Anthropic's Claude, Google's Gemini, and OpenAI's GPT).

---

## ✨ Key Features

* **Multi-VCS Support:** Native integration with **GitHub Actions** and **GitLab CI**.
* **Multi-Model Support:** Choose between **Claude Sonnet 4.6** (Anthropic), **Gemini 2.5 Pro** (Google), or **GPT-4o** (OpenAI).
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
  - remote: 'https://raw.githubusercontent.com/akalongman/universal-ai-reviewer/1.2.0/gitlab-template.yml'

variables:
  # Pin the cloned reviewer code to the same ref as the template you include above.
  # Defaults to "main" if unset, which can drift away from the pinned template.
  # AI_REVIEWER_REF is only honored by template versions 1.2.0 and later.
  AI_REVIEWER_REF: "1.2.0"

# Ensure you have a 'review' stage defined
stages:
  - build
  - test
  - review
```

---

## 🚦 Allowing Merges on AI Failure (Soft Fails)

By default, this tool acts as a strict gatekeeper: if it detects `🔴 Critical Issues`, it will fail the CI job and block the Merge/Pull Request. 

If you want the AI to only act as an advisor (failing the job with a warning, but still allowing developers to merge their code), you should use your platform's native "Soft Fail" flags:

**For GitHub Actions:**
Add `continue-on-error: true` to the step in your workflow:
```yaml
- name: AI Code Review
  uses: akalongman/universal-ai-reviewer@main
  continue-on-error: true # <--- Allows merging even if critical issues are found
  with:
    # ...
```

**For GitLab CI:**
Override the included job to allow failures in your `.gitlab-ci.yml`:
```yaml
auto_ai_review:
  allow_failure: true # <--- Job turns orange instead of red, allowing merges
```

---

## ⚙️ Configuration Variables

The script automatically detects whether it is running in GitHub or GitLab. You can tune the behavior using the following environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `AI_PROVIDER` | `anthropic` | Set to `openai` or `gemini` to use other models. |
| `AI_MODEL` | Provider Dependent | Defaults to `claude-sonnet-4-6`, `gemini-2.5-pro`, or `gpt-4o`. |
| `AI_MAX_TOKENS` | `8192` | The maximum length of the AI response. |
| `AI_TEMPERATURE` | *(unset)* | Controls randomness (0.0 is strict, 1.0 is creative). If left unset, the parameter is omitted from the request entirely so the provider's own default applies. See the note below before setting this. |
| `ANTHROPIC_API_KEY` | - | Required if using the Anthropic provider. |
| `GEMINI_API_KEY` | - | Required if `AI_PROVIDER` is set to `gemini`. |
| `OPENAI_API_KEY` | - | Required if `AI_PROVIDER` is set to `openai`. |
| `GITLAB_TOKEN` | - | Required for GitLab (PAT with `api` scope). |
| `GITHUB_TOKEN` | Auto | Automatically handled by GitHub Actions. |
| `AI_FETCH_CHANGED_FULL` | `false` | When `true`, the reviewer fetches the full head content of each changed file alongside the diff. See "Full file context (preview)" below. |
| `AI_FETCH_RELATED_FILES` | `false` | When `true`, the reviewer also fetches files imported by changed files (JS, TS, PHP in v1). See "Full file context (preview)" below. |
| `AI_FETCH_RELATED_DEPTH` | `1` | Maximum number of import hops to follow when `AI_FETCH_RELATED_FILES=true`. `0` disables related fetching entirely. |

### A note on `AI_TEMPERATURE`

Leaving `AI_TEMPERATURE` unset is the safest default for cross-provider use. When the variable is absent, the reviewer omits the parameter from the API request and lets each provider apply its own default (typically 1.0). This matters because several current models reject or constrain the `temperature` field:

* **OpenAI reasoning models** (the `o1`, `o3`, `o4`, and some `gpt-5` variants) reject any `temperature` value and return a 400 error if one is supplied.
* **Anthropic Claude with extended thinking enabled** requires `temperature` to be exactly `1.0`. Any other value is rejected by the API.
* **Google Gemini thinking configurations** accept the parameter but it has little effect in thinking mode.

Set `AI_TEMPERATURE` explicitly only when you have picked a specific model and you know that value is supported.

### Full file context (preview)

By default the reviewer sees only the unified diff, which can cause the model to flag "missing imports" or "undefined functions" that actually exist elsewhere in the file. To give the AI broader context, opt in with the following variables (off by default):

* `AI_FETCH_CHANGED_FULL=true` fetches the head version of every changed file and embeds it in the prompt under a `**Full File Context:**` section.
* `AI_FETCH_RELATED_FILES=true` additionally extracts imports from each changed file and fetches the resolved files. JavaScript, TypeScript, and PHP are supported in v1 (other languages still benefit from `AI_FETCH_CHANGED_FULL`, they simply skip import extraction).
* `AI_FETCH_RELATED_DEPTH=N` controls how many hops to follow. `0` disables, `1` (default) fetches only direct imports, higher values traverse transitively.

Resolution rules:

* **JavaScript / TypeScript**: relative imports are resolved against the source file. The reviewer reads `tsconfig.json` (honoring `compilerOptions.paths` aliases) and `package.json` (top level `imports`) at the repository root. The standard Node resolution suffixes (`.ts`, `.tsx`, `.js`, `.jsx`, `index.*`) are tried in order. Webpack, vite, and rollup specific aliases are not honored in v1.
* **PHP**: namespaces are resolved against `composer.json` `autoload.psr-4` and `autoload-dev.psr-4` mappings at the repository root. `classmap` and `files` are not supported in v1.

Limitations and failure modes:

* Configuration files are read from the repository root only. Monorepos with multiple `tsconfig.json` or `composer.json` files are not fully supported in v1.
* Unresolved import specifiers are silently skipped rather than logged as errors.
* If the assembled prompt would exceed the active model's context window (with a 20 percent safety margin), the job fails with a message asking you to disable the feature, lower the depth, or shrink the PR. The reviewer does not silently truncate fetched content.

Cost trade off: enabling these variables substantially increases input tokens (and therefore cost and latency). The feature is most valuable for small to medium PRs where the model would otherwise hallucinate from missing context.

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
*.png
*.jpg
*.jpeg
*.gif
*.ico
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
