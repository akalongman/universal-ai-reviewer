## 1. Foundations

- [ ] 1.1 Add `tree-sitter`, `tree-sitter-javascript`, `tree-sitter-typescript`, and `tree-sitter-php` to `requirements.txt`
- [ ] 1.2 Add `AI_FETCH_CHANGED_FULL`, `AI_FETCH_RELATED_FILES` (booleans, default false) and `AI_FETCH_RELATED_DEPTH` (int, default 1) to `reviewer/config.py`, using the existing truthy convention for the booleans
- [ ] 1.3 Validate that `AI_FETCH_RELATED_DEPTH` parses as a non negative integer; fail Config init with a clear message otherwise
- [ ] 1.4 Add Config tests confirming default values, truthy parsing, and the invalid depth failure mode

## 2. VCS content fetching contract

- [ ] 2.1 Add abstract `get_file_content(path: str, ref: str) -> Optional[str]` to `VCSProvider` in `reviewer/vcs_providers.py`
- [ ] 2.2 Implement `get_file_content` on `GitHubProvider` using `self.repo.get_contents(path, ref=ref)`, translating 404 to `None`
- [ ] 2.3 Implement `get_file_content` on `GitLabProvider` using `self.project.files.get(file_path=path, ref=ref)`, translating `GitlabGetError` with 404 status to `None`
- [ ] 2.4 Expose `head_sha` on both provider instances (`self.pr.head.sha` for GitHub, `self.mr.sha` for GitLab), populated at construction
- [ ] 2.5 Add provider tests for `get_file_content` covering: file exists, file missing (returns None), unrelated API error propagates

## 3. Per language import extractors (tree sitter)

- [ ] 3.1 Create `reviewer/context_fetcher.py` with lazy `tree_sitter` import guarded behind a `_ensure_tree_sitter_available()` helper that raises a clear error if the grammars cannot be loaded
- [ ] 3.2 Implement `extract_imports_js(source: str) -> set[str]` covering `import ... from`, `import type ... from`, dynamic `import('x')`, and `export ... from`
- [ ] 3.3 Implement `extract_imports_ts(source: str) -> set[str]` (TypeScript grammar; semantics mirror JS plus type only imports)
- [ ] 3.4 Implement `extract_imports_php(source: str) -> set[str]` covering `use Namespace\Class;` and grouped `use Namespace\{A, B};`
- [ ] 3.5 Add extractor tests including the negative scenario "import-looking string inside a string literal returns empty set"

## 4. Per language path resolvers

- [ ] 4.1 Implement `resolve_js_path(specifier: str, from_file: str) -> Optional[str]` honoring `tsconfig.json` `compilerOptions.paths`, `package.json` top level `imports`, and the standard Node resolution suffixes (`.js`, `.ts`, `.tsx`, `.jsx`, `index.*`)
- [ ] 4.2 Implement `resolve_php_path(specifier: str) -> Optional[str]` honoring `composer.json` `autoload.psr-4` and `autoload-dev.psr-4`
- [ ] 4.3 Read repo root config files once at fetcher init; cache parsed JSON in memory
- [ ] 4.4 Add resolver tests for: relative JS import, tsconfig alias, PSR-4 mapping, unresolved specifier (returns None silently)

## 5. Fetcher orchestration

- [ ] 5.1 Implement a `ContextFetcher` class in `reviewer/context_fetcher.py` whose constructor takes the VCS provider, the Config, and the loaded `.aiignore` patterns
- [ ] 5.2 Implement `fetch_for_diff(diff_text: str) -> dict[str, str]`: parse the diff's `b/` paths, fetch each changed file's head content when `AI_FETCH_CHANGED_FULL=true`
- [ ] 5.3 When `AI_FETCH_RELATED_FILES=true`, traverse imports via the per language extractor + resolver, up to `AI_FETCH_RELATED_DEPTH` hops
- [ ] 5.4 Cache results by `(path, ref)`; cache negative lookups as `None` so re-queries during traversal are free
- [ ] 5.5 Apply the same `.aiignore` filter to fetched paths (both changed and related) as `filter_diff` applies to the diff
- [ ] 5.6 For changed files in unsupported languages: fetch full content when `AI_FETCH_CHANGED_FULL=true`, skip related resolution silently
- [ ] 5.7 Add orchestration tests covering: dedup across imports, depth bounding, unsupported language fallback, `.aiignore` short circuiting

## 6. Prompt integration

- [ ] 6.1 Add optional `fetched_files: dict[str, str] | None = None` parameter to `build_prompts` in `reviewer/prompts.py`
- [ ] 6.2 When `fetched_files` is non empty, emit a `**Full File Context:**` section between `**MR Description:**` and the diff fence; each file gets `**File: <path>**` followed by a fenced code block of the content
- [ ] 6.3 Extend the system prompt with one sentence instructing the model to treat the `**Full File Context:**` section as read only context for the diff
- [ ] 6.4 Preserve the existing category header contract (`🔴 Critical Issues`, `🟡 Suggestions`, `🟢 Nitpicks/Praise`) and the OMIT when empty rule verbatim
- [ ] 6.5 Add prompt tests for: single fetched file present, no fetched files (no section emitted), category header preservation

## 7. Context window overflow handling

- [ ] 7.1 Add a `CONTEXT_WINDOWS` lookup table mapping model name to its input context window size (cover the three current defaults at minimum: `claude-sonnet-4-6`, `gemini-2.5-pro`, `gpt-4o`)
- [ ] 7.2 Implement an estimator: `estimated_tokens = len(system_prompt + user_prompt) // 4`
- [ ] 7.3 Apply a 20 percent safety margin against the model's window; if exceeded, raise a `ContextTooLargeError` with the actionable message from the spec
- [ ] 7.4 In `reviewer/main.py`, catch `ContextTooLargeError` and route it through the existing error path (update placeholder, exit 1)
- [ ] 7.5 Add overflow tests using a mocked oversized prompt

## 8. Pipeline integration

- [ ] 8.1 In `reviewer/main.py`, instantiate `ContextFetcher` after the placeholder comment is created (step 4) and call it before `build_prompts` (step 5)
- [ ] 8.2 When either fetch env var is true, append "(Fetching file context...)" to the placeholder comment body so reviewers see what is happening
- [ ] 8.3 Thread the `fetched_files` dict into the `build_prompts` call site
- [ ] 8.4 Ensure that with both env vars unset the fetcher is not instantiated at all (no `tree_sitter` import attempted)
- [ ] 8.5 Manual sanity check: run `python -m pytest tests/ -v` and confirm all pre existing tests still pass

## 9. Documentation

- [ ] 9.1 Update `README.md` Configuration Variables table with `AI_FETCH_CHANGED_FULL`, `AI_FETCH_RELATED_FILES`, `AI_FETCH_RELATED_DEPTH`
- [ ] 9.2 Add a new README section "Full file context (preview)" describing the three env vars, the v1 supported languages (JS, TS, PHP), the resolution rules, the known limitations (repo root configs only, no webpack aliases), the overflow failure mode, and the cost trade off
- [ ] 9.3 Update `CLAUDE.md` to note the new `context-fetching` capability and reference the spec at `openspec/specs/context-fetching/spec.md` once the change is archived

## 10. Verification

- [ ] 10.1 All new tests pass via `python -m pytest tests/ -v` from the repo root
- [ ] 10.2 All pre existing tests still pass (zero changes required to them)
- [ ] 10.3 With both env vars unset, a manual run of `python reviewer/main.py` against a synthetic `mr_diff.txt` produces a prompt byte identical to today's baseline
- [ ] 10.4 With `AI_FETCH_CHANGED_FULL=true` and a small mocked diff, a manual run produces a prompt containing the expected `**Full File Context:**` section
