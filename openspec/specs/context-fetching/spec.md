# context-fetching Specification

## Purpose

Defines the opt in retrieval of full file content (and optionally the content of files imported by changed files) for inclusion in the AI review prompt. Covers env var activation, tree-sitter import extraction for JS, TS, and PHP, per language path resolution, the VCS content fetching contract, in-run caching, `.aiignore` alignment, prompt section formatting, and the context window overflow failure mode. Exists to eliminate the false positive class where the reviewer flags issues that are actually resolved by code outside the diff window.

## Requirements
### Requirement: Opt in activation by environment variables

The reviewer SHALL fetch full file content only when explicitly enabled by environment variables. When both `AI_FETCH_CHANGED_FULL` and `AI_FETCH_RELATED_FILES` are unset or set to a falsy value, the pipeline MUST behave byte identically to the diff only baseline. The set of truthy values MUST match the existing convention used elsewhere in `Config` (case insensitive match against `"true"`, `"1"`, `"yes"`).

#### Scenario: Both env vars unset
- **WHEN** the reviewer runs and neither `AI_FETCH_CHANGED_FULL` nor `AI_FETCH_RELATED_FILES` is set
- **THEN** no VCS file fetch occurs, the user prompt contains no "Full File Context" section, and the placeholder comment text matches the pre-feature baseline

#### Scenario: AI_FETCH_CHANGED_FULL only
- **WHEN** `AI_FETCH_CHANGED_FULL=true` and `AI_FETCH_RELATED_FILES` is unset
- **THEN** the reviewer fetches the head content of each file appearing in the diff, includes it in the user prompt, and does NOT invoke any import extractor

#### Scenario: AI_FETCH_RELATED_FILES requires changed full to be useful
- **WHEN** `AI_FETCH_RELATED_FILES=true` and `AI_FETCH_CHANGED_FULL=false`
- **THEN** the reviewer fetches related files but does NOT include the changed files in full; the diff alone represents changed files

### Requirement: Bounded related file traversal

When `AI_FETCH_RELATED_FILES=true`, the reviewer SHALL traverse the import graph of changed files up to a depth bounded by `AI_FETCH_RELATED_DEPTH`. The depth MUST default to `1` when the variable is unset. A depth of `0` MUST be treated as equivalent to `AI_FETCH_RELATED_FILES=false`. Non integer or negative values MUST cause `Config` initialization to fail with a clear error message.

#### Scenario: Default depth fetches direct imports only
- **WHEN** `AI_FETCH_RELATED_FILES=true`, `AI_FETCH_RELATED_DEPTH` is unset, and a changed file `a.js` imports `b.js` which imports `c.js`
- **THEN** `b.js` is fetched and `c.js` is NOT fetched

#### Scenario: Depth of 2 follows two hops
- **WHEN** `AI_FETCH_RELATED_FILES=true`, `AI_FETCH_RELATED_DEPTH=2`, and the same import graph as above
- **THEN** both `b.js` and `c.js` are fetched

#### Scenario: Invalid depth fails fast
- **WHEN** `AI_FETCH_RELATED_DEPTH=banana`
- **THEN** `Config` initialization raises an error stating that the variable must be a non negative integer, and the run exits before any VCS call is made

### Requirement: Tree sitter import extraction for v1 languages

The reviewer SHALL extract import specifiers from changed files using tree sitter grammars for JavaScript, TypeScript, and PHP. Each extractor MUST return the set of module specifier strings appearing in import statements, deduplicated.

#### Scenario: JavaScript ES import
- **WHEN** a changed file `src/handler.js` contains `import { foo } from './utils';`
- **THEN** the JavaScript extractor returns a set containing `'./utils'`

#### Scenario: TypeScript type import
- **WHEN** a changed file `src/types.ts` contains `import type { User } from './models';`
- **THEN** the TypeScript extractor returns a set containing `'./models'`

#### Scenario: PHP namespaced use
- **WHEN** a changed file `src/Service.php` contains `use App\Services\UserService;`
- **THEN** the PHP extractor returns a set containing `App\Services\UserService`

#### Scenario: Imports inside strings are not extracted
- **WHEN** a changed file contains the literal string `"import x from 'y'"` inside a string body and no real import statement
- **THEN** the extractor returns an empty set (tree sitter ignores content inside string nodes)

### Requirement: Per language path resolution

The reviewer SHALL map each import specifier to a repository file path using language specific resolution rules read from the repository root.

For JavaScript and TypeScript, the resolver MUST:
- read `tsconfig.json` if present and honor `compilerOptions.paths` aliases;
- read `package.json` if present and honor a top level `"imports"` map;
- otherwise apply the standard Node resolution algorithm (try the specifier with `.js`, `.ts`, `.tsx`, `.jsx` suffixes; then try `<specifier>/index.{js,ts,tsx,jsx}`).

For PHP, the resolver MUST read `composer.json` if present and honor `autoload.psr-4` and `autoload-dev.psr-4` mappings to translate the namespace prefix into a directory path, then append the remaining namespace segments as directories and `.php` as the file extension.

Unresolved specifiers SHALL be silently skipped (omitted from the fetch list); they MUST NOT raise.

#### Scenario: Relative JS import resolved by extension
- **WHEN** `src/handler.js` imports `./utils` and `src/utils.js` exists in the repo
- **THEN** the resolver returns `src/utils.js`

#### Scenario: tsconfig path alias
- **WHEN** `tsconfig.json` declares `"compilerOptions": {"paths": {"@app/*": ["src/*"]}}` and a file imports `@app/utils`
- **THEN** the resolver returns `src/utils.ts` (or `.js`, whichever exists first per the resolution order)

#### Scenario: PSR-4 PHP namespace
- **WHEN** `composer.json` declares `"App\\": "src/"` under `autoload.psr-4` and a file imports `App\Services\UserService`
- **THEN** the resolver returns `src/Services/UserService.php`

#### Scenario: Unresolved specifier is skipped
- **WHEN** a file imports `nonexistent-package` and no resolution rule matches a file in the repo
- **THEN** the resolver returns nothing, no fetch is attempted, no error is raised, and processing continues for remaining imports

### Requirement: Unsupported language fallback

When `AI_FETCH_CHANGED_FULL=true` and a changed file's language has no v1 tree sitter extractor (anything other than JS, TS, PHP), the reviewer SHALL still fetch and include the full content of that changed file. Related file resolution SHALL be skipped for that file without raising.

#### Scenario: Go file with both vars enabled
- **WHEN** `AI_FETCH_CHANGED_FULL=true`, `AI_FETCH_RELATED_FILES=true`, and a changed file is `main.go`
- **THEN** the reviewer fetches the full content of `main.go` and includes it in the prompt, does NOT attempt Go import extraction, and does NOT fail the run

#### Scenario: Markdown file with both vars enabled
- **WHEN** `AI_FETCH_CHANGED_FULL=true` and the diff touches `README.md`
- **THEN** the reviewer fetches the full content of `README.md` and includes it in the prompt; related file resolution is skipped silently

### Requirement: VCS content fetching contract

Each concrete `VCSProvider` implementation SHALL expose `get_file_content(path: str, ref: str) -> Optional[str]` that returns the text content of a repository file at a given ref, or returns `None` when the file does not exist at that ref. API errors that semantically mean "file not found" (HTTP 404, GitLab `GitlabGetError` with 404 status, etc.) MUST be translated to `None`. Other API errors MUST propagate and follow the existing top level error handling in `main.py` (placeholder comment is updated with the error message and the run exits 1).

#### Scenario: File exists at head SHA
- **WHEN** the reviewer requests `src/handler.js` at the head SHA of the current PR/MR
- **THEN** the VCS provider returns the text content of that file at that SHA

#### Scenario: File missing at ref
- **WHEN** the reviewer requests a path that does not exist at the supplied ref
- **THEN** the VCS provider returns `None` and the reviewer continues processing remaining files

#### Scenario: Transient API error propagates
- **WHEN** the VCS API returns HTTP 500 for a content fetch
- **THEN** the run fails via the existing top level error handler; the placeholder comment is updated with the error message and the process exits 1

### Requirement: Prompt section formatting

When at least one file has been successfully fetched, the reviewer SHALL include a `**Full File Context:**` section in the user prompt, placed between `**MR Description:**` and the diff fence. Each fetched file MUST appear as a header line `**File: <path>**` followed by a fenced code block containing the file's text. The system prompt MUST be updated to instruct the model to treat fetched files as read only context for the diff. The category header contract (`🔴 Critical Issues` / `🟡 Suggestions` / `🟢 Nitpicks/Praise`) and the OMIT when empty rule MUST be preserved verbatim, so that the gatekeeper logic in `main.py` continues to work without modification.

#### Scenario: Single fetched file
- **WHEN** one file `src/handler.js` has been fetched
- **THEN** the user prompt contains `**Full File Context:**` followed by `**File: src/handler.js**` and a code fence with the file's content, all placed before the ```diff fence

#### Scenario: No files fetched
- **WHEN** the feature is enabled but no files were fetched (e.g., all changed files were ignored by `.aiignore`)
- **THEN** the user prompt does NOT contain a `**Full File Context:**` section and the prompt format matches the pre-feature baseline

#### Scenario: Category header contract preserved
- **WHEN** any combination of the new env vars is set and the AI response contains no critical issues
- **THEN** the AI is still instructed to omit the `🔴 Critical Issues` header entirely, and the gatekeeper in `main.py` exits 0

### Requirement: Context window overflow handling

When the assembled prompt's estimated input size exceeds the active model's context window (with a 20 percent safety margin), the reviewer SHALL fail the run with an actionable error message and exit non zero. Fetched file content MUST NOT be silently truncated or selectively dropped to fit. Estimation MAY use a character heuristic for v1.

#### Scenario: Overflow detected before API call
- **WHEN** the assembled `system_prompt + user_prompt` is estimated to exceed the active model's context window
- **THEN** the placeholder comment is updated with the message "context too large: disable AI_FETCH_FULL_FILES, lower AI_FETCH_RELATED_DEPTH, or reduce the PR scope" and the process exits 1

#### Scenario: Prompt under the limit proceeds normally
- **WHEN** the estimated size is within the model's context window minus the safety margin
- **THEN** the reviewer proceeds with the API call, posts the review, and runs the gatekeeper as usual

### Requirement: .aiignore filtering applies to fetched content

Files matching patterns in `.aiignore` SHALL be excluded from full content fetching and from related file resolution. The fetcher MUST consume the `.aiignore` pattern list via the same loader currently used by `filter_diff` so that "ignored" remains a single, consistent concept across the diff section and the new full file section.

#### Scenario: package-lock.json is in .aiignore and appears in the diff
- **WHEN** `.aiignore` contains `package-lock.json` and the diff touches `package-lock.json`
- **THEN** the reviewer does NOT fetch `package-lock.json` and does NOT extract imports from it

#### Scenario: An ignored file is the resolution target of a real import
- **WHEN** a changed file imports a path that resolves to a file matching an `.aiignore` pattern
- **THEN** the fetcher silently skips that file (treats it as if the resolution had failed)

### Requirement: Fetched content cache within a single run

The reviewer SHALL cache fetched file content for the duration of one review run, keyed by `(path, ref)`. When multiple changed or related files target the same `(path, ref)` pair, the VCS provider's `get_file_content` MUST be invoked at most once for that pair. Negative results (file not found) MUST also be cached so that retries for a known absent file are not issued during transitive traversal.

#### Scenario: Two changed files import the same utility
- **WHEN** two changed files both import `./utils` that resolves to `src/utils.js`
- **THEN** `get_file_content("src/utils.js", head_sha)` is invoked exactly once and `src/utils.js` appears exactly once in the user prompt

#### Scenario: A known absent file is not re-queried
- **WHEN** a depth 1 traversal fails to resolve and fetch `src/missing.js`, and a depth 2 traversal encounters the same path
- **THEN** the cached `None` result is reused and no additional API call is made

