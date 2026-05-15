## Context

Today the reviewer is a pure function of one input: the unified diff in `mr_diff.txt`. The CI runners generate that diff, drop it on disk, and `reviewer/main.py` feeds it to the model. The model never sees the surrounding code, so it cannot tell whether an "undefined function" call is actually defined two screens above the diff window, or whether the contract a caller relies on still holds in the imported module.

This change introduces an optional second input: the head content of changed files, and (transitively, bounded by depth) the content of files those changed files import. Implementation crosses several existing capability boundaries (`vcs-integration`, `configuration`, `prompt-engineering`, `pipeline-orchestration`) but the *requirements* cluster naturally into one new capability, `context-fetching`. This design covers HOW the new module fits.

## Goals / Non-Goals

**Goals:**

- Make full content fetching opt in, default off, byte identical behaviour when disabled.
- Support tree-sitter based import extraction for JavaScript, TypeScript, and PHP in v1.
- Preserve the existing gatekeeper contract verbatim (the AI's `🔴 Critical Issues` header semantics and the exit code policy in `main.py` are untouched).
- Fail loudly on context window overflow rather than silently degrading review quality.
- Add no required dependencies. New deps install only when the feature is enabled, or are accepted as a small fixed cost on every install (decided below).

**Non-Goals:**

- Native parallelism of file fetches. A v1 may be slower; if measurement justifies, parallelism comes later.
- Support for inline review comments (already tracked separately in `TODO.md`).
- Support for languages outside JS/TS/PHP in v1. Other languages still benefit from `AI_FETCH_CHANGED_FULL`; they just skip related file resolution.
- Resolving webpack, vite, or rollup specific aliases. v1 honors `tsconfig.json` and `package.json` only.
- A diff-aware "show me only the symbols you reference" optimization. Files are fetched whole.

## Decisions

### 1. Tree-sitter package layout

Use `tree-sitter` (the core binding) plus three explicit grammar packages: `tree-sitter-javascript`, `tree-sitter-typescript`, `tree-sitter-php`.

Considered: the `tree-sitter-languages` bundle. Rejected because it ships ~50 grammars (~30 MB), most of which v1 does not use, and its version cadence is slower than per-grammar packages. The explicit list keeps the dependency surface tight and makes future grammar additions a deliberate proposal rather than a silent capability change.

### 2. New module placement: single file, not a package

Add `reviewer/context_fetcher.py`. Per-language extractors live as top-level functions inside the same module. Path resolvers similarly.

Considered: a `reviewer/context_fetcher/` sub-package with one module per language. Rejected because (a) the per-language code is ~50 lines each, not enough to warrant a package, and (b) the existing import asymmetry in this project (sibling imports in `main.py` vs package imports in tests) is brittle; adding a sub-package widens that brittleness for no win.

### 3. Pipeline insertion point

Insert the fetch step between current step 3 ("read mr_diff.txt") and current step 4 ("create placeholder comment").

Rationale: the placeholder comment should appear *before* the (potentially slow) fetch step, so reviewers see the "thinking" indicator while context is being assembled. So the order becomes: read diff, **fetch context** (skipped when both env vars off), placeholder, build prompts, call AI, edit placeholder, gatekeeper.

Wait, that puts fetching before the placeholder. Reconsidering: placing the placeholder before the fetch step is the better choice for live feedback. Final order: read diff, placeholder, **fetch context**, build prompts, call AI, edit placeholder, gatekeeper. The placeholder text gains one sentence: "(Fetching file context...)". When the feature is off, behaviour is byte identical because the fetch step is a no op that returns `{}`.

### 4. Token counting strategy

For v1, estimate prompt size as `len(prompt) // 4` characters per token. Compare against a hardcoded table of model context windows in `reviewer/context_fetcher.py`. Add a 20% safety margin.

Considered: provider-specific token counters (`tiktoken`, `anthropic.count_tokens`, `genai.count_tokens`). Rejected for v1 because they either add a heavy dependency (`tiktoken`) or require an API call before the API call (Anthropic's). The character heuristic is conservative for code (which tends to be slightly more dense than 4 chars/token in tiktoken) and the 20% buffer absorbs the error. If real world usage shows this is too pessimistic or too optimistic, swap in a per-provider counter as a follow up change.

### 5. Path resolution policy

- **JS/TS**: read `tsconfig.json` and `package.json` (at the repo root only) at fetcher init time. Honor `compilerOptions.paths` aliases and the standard Node resolution algorithm (`.js`, `.ts`, `.tsx`, `index.js`, etc.). Do NOT execute node, do NOT shell out.
- **PHP**: read `composer.json` (at the repo root only). Honor `autoload.psr-4` and `autoload-dev.psr-4` mappings. Skip `classmap` and `files` entries (out of scope for v1).
- **Both**: silent skip on unresolved imports. The user prompt gracefully omits files that could not be located.

Considered: walking up from each source file to find the nearest `tsconfig.json` or `composer.json`. Rejected for v1 because monorepo support is a separate non-trivial concern; the repo-root-only rule is documented as a known limitation in the README.

### 6. VCS content fetch contract

```python
class VCSProvider(ABC):
    @abstractmethod
    def get_file_content(self, path: str, ref: str) -> Optional[str]:
        """Return the file's text at `ref`, or None if the file does not exist at that ref."""
```

`ref` for changed files is the head SHA of the PR/MR. The head SHA is exposed differently per platform:

- GitHub: `self.pr.head.sha` (already available via PyGithub on `GitHubProvider`).
- GitLab: `self.mr.sha` (already available via python-gitlab on `GitLabProvider`).

Both are read once at fetcher init and reused across all `get_file_content` calls.

### 7. In-run cache

A plain `dict[tuple[str, str], Optional[str]]` lives on the fetcher instance. Keys are `(path, ref)`. Misses are also cached (as `None`) so a known-absent file is not re-queried during transitive traversal.

### 8. Feature gating of imports

Import `tree_sitter` and the grammar packages lazily, inside the fetch entry point, only when `AI_FETCH_RELATED_FILES=true`. If the import fails (broken install, unsupported platform), the run fails with: "tree-sitter packages are required for AI_FETCH_RELATED_FILES; install them or unset the variable". When `AI_FETCH_RELATED_FILES` is false, the import is never attempted, and a broken `tree-sitter` install does not affect existing users.

### 9. .aiignore alignment

The existing `.aiignore` filter applies to the diff before fetching begins. The fetcher receives the *post filter* set of changed file paths and never sees ignored files. Related file resolution also runs the resolved path through the same `fnmatch` set before fetching. This keeps "ignored" a single, consistent concept.

## Risks / Trade-offs

[Tree-sitter install failures on niche platforms (musl, certain ARM CI runners)] → Lazy import + clear error message tells the operator to either fix the env or disable the feature. No silent failure.

[JS/TS path resolution misses webpack-style aliases] → Documented as a v1 limitation in the README. Unresolved imports are silently skipped (review still runs, just without that file). A follow up change can wire webpack aliases if real-world demand appears.

[Token estimation imprecision] → 20% buffer absorbs heuristic error. If runs start failing for "context too large" when the prompt was actually fine, swap in a real tokenizer. If runs start succeeding when the prompt was actually over, the API returns its own error and the existing error path handles it.

[Fetch latency dominates run time for large PRs] → v1 accepts this. Mitigation path: parallel fetches via `concurrent.futures.ThreadPoolExecutor`. Tracked as a future enhancement, not v1 scope.

[New tree-sitter grammars add ~10 MB install footprint] → Acceptable for a CI tool. Documented in the README. If footprint becomes a complaint, switch to feature-gated install (e.g., `pip install universal-ai-reviewer[context]`) as a follow up.

[A consumer enables AI_FETCH_RELATED_FILES=true but their language is not in v1] → Per the spec, changed files still get fetched in full; related file resolution silently skips. Logged at info level so the operator can see why no related files appeared.

## Migration Plan

The feature is opt in, so there is no migration burden on existing consumers. After this change merges:

1. Update `requirements.txt` with the four new dependencies.
2. Update the README with a new section documenting the three env vars, the supported languages, the resolution rules, and the known limitations (no webpack aliases, no monorepo config walking).
3. No changes required in `action.yaml` or `gitlab-template.yml`. New env vars flow through existing mechanisms.

Rollback: revert the change. Consumers that had set `AI_FETCH_CHANGED_FULL` or `AI_FETCH_RELATED_FILES` will see those vars become no ops; behaviour returns to the pre-feature baseline.

## Open Questions

- Do we want to log the list of fetched files in the action's stdout for debuggability? (Suggested: yes, behind a `AI_DEBUG_FETCH=true` flag. Not in v1 scope unless trivial.)
- Do we want a hard upper bound on the number of fetched files even when token estimation passes? (Suggested: no for v1; the token estimation gate is the only limit.)
- For Anthropic's extended thinking mode, fetched files arrive as plain user-prompt content; no special routing needed. Worth confirming in design review.
