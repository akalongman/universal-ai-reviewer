## Why

The reviewer currently sees only the unified diff (`mr_diff.txt`); no surrounding code, no callers, no callees. This produces obsolete reviews. The model flags "missing imports" when the import is elsewhere in the file, complains about "undefined functions" defined two lines below the diff window, and cannot reason about cross capability consistency (a caller in file A relying on a contract defined in file B). The current system prompt asks the AI to be cautious about these cases, but caution is a weak fix for missing context. Giving the agent the actual file content (and optionally the files imported by changed files) closes this false positive class entirely.

## What Changes

- **NEW**: opt in download of changed files in full. Enabled via `AI_FETCH_CHANGED_FULL=true`. Off by default.
- **NEW**: opt in download of related files (files imported or referenced by changed files). Enabled via `AI_FETCH_RELATED_FILES=true`. Off by default.
- **NEW**: configurable traversal depth via `AI_FETCH_RELATED_DEPTH=<integer>`, default 1. Higher values follow imports transitively.
- **NEW**: tree-sitter based import extraction for JavaScript, TypeScript, and PHP in v1. Files in other languages still receive full content fetching when `AI_FETCH_CHANGED_FULL=true`; related file resolution simply skips them.
- **NEW**: per language path resolution. JS/TS reads `tsconfig.json` and `package.json` for path aliases; PHP reads `composer.json` PSR-4 autoload map.
- **NEW**: `VCSProvider` abstract class gains a `get_file_content(path: str, ref: str) -> Optional[str]` method. Both `GitHubProvider` and `GitLabProvider` implement it via each platform's file content API.
- **NEW**: the user prompt grows a `**Full File Context:**` section listing each fetched file with its path and contents, placed between `**MR Description:**` and the ```diff block.
- **NEW**: context overflow handling. If the assembled prompt would exceed the model's context window, the job fails with a clear message instructing the operator to disable the feature, lower the depth, or shrink the PR. No silent truncation.
- New Python runtime dependencies: `tree-sitter`, plus grammar packages for the v1 languages.
- New tests: mocked VCS `get_file_content` for each provider, tree-sitter import extraction per language, path resolution rules per language, and end to end prompt assembly with fetched content.

## Capabilities

### New Capabilities
- `context-fetching`: opt in retrieval of full file content and imported file content for inclusion in the AI review prompt. Covers the env var contract, tree-sitter based import extraction, per language path resolution conventions, the VCS content fetching contract, prompt section formatting, traversal semantics with depth bounding, and the overflow failure mode.

### Modified Capabilities
<!-- No existing capability spec files live under openspec/specs/ yet
     (per the project's progressive disclosure rule, specs are extracted
     only when a real change warrants it). Cross capability interactions
     are documented under Impact below. The existing gatekeeper contract
     between prompt-engineering and pipeline-orchestration is preserved
     verbatim by this change. -->

## Impact

### Code

- `reviewer/config.py`: three new env vars (`AI_FETCH_CHANGED_FULL`, `AI_FETCH_RELATED_FILES`, `AI_FETCH_RELATED_DEPTH`) loaded and exposed on `Config`. Validation: depth must parse as a non negative integer when provided.
- `reviewer/vcs_providers.py`: new `get_file_content` method on the abstract base; concrete implementations for `GitHubProvider` (via `repo.get_contents(path, ref=sha)`) and `GitLabProvider` (via `project.files.get(file_path=path, ref=sha)`).
- `reviewer/prompts.py`: new optional argument `fetched_files: dict[str, str]` on `build_prompts`. When non empty, the user prompt grows a `**Full File Context:**` section that the system prompt is updated to reference.
- `reviewer/main.py`: a new step inserted between step 3 ("read diff") and step 5 ("build prompts") that, when either fetch env var is true, invokes the context fetcher and threads the result into `build_prompts`. The step is fully skipped when both env vars are unset, preserving today's behaviour byte for byte.
- New module: `reviewer/context_fetcher.py`. Houses tree-sitter grammar bootstrapping, per language import extractors, path resolution, traversal with depth cap, VCS fetch orchestration, and assembly of the `fetched_files` dict consumed by `build_prompts`.

### Cross capability impact (relative to the capability map in `openspec/config.yaml`)

- `configuration`: adds three env vars. No change to defaults for unrelated keys.
- `vcs-integration`: extends the abstract `VCSProvider` contract with `get_file_content`. Existing methods unchanged. Tests must mock the new method even when not exercised.
- `pipeline-orchestration`: the seven step pipeline becomes eight when the feature is enabled, seven when it is not. The exit code gatekeeper contract is untouched.
- `prompt-engineering`: the user prompt gains one section. The category header contract (`🔴 Critical Issues` / `🟡 Suggestions` / `🟢 Nitpicks/Praise`) and the OMIT-when-empty rule are preserved verbatim, so no coordinated update with `pipeline-orchestration` is required.
- `llm-integration`: unaffected. The streaming chunk concatenation contract continues to apply, just over a larger input prompt.
- `ci-runners`: unaffected. New env vars flow through the existing `env:` block on the GitHub side and `variables:` on the GitLab side. The GitLab template re-clone semantics (consumers pinning a tag still pull `main` for the clone) apply unchanged because no template files are touched.
- `diff-handling`: the existing diff filter and 50000 character truncation remain. The fetcher reads the diff to learn changed paths (the `b/` path on each `diff --git` header), then operates independently.

### Dependencies and footprint

- Adds `tree-sitter` and grammar packages to `requirements.txt`. Roughly 10 MB additional install on cold start.
- When enabled, model input tokens grow substantially. This is the user's intent and is documented in the README; cost trade off is the operator's call.

### Backward compatibility

Full. With both `AI_FETCH_CHANGED_FULL` and `AI_FETCH_RELATED_FILES` unset, the pipeline, prompt, exit codes, and dependencies a consumer sees at runtime are identical to today's. Existing tests must continue to pass without modification.
