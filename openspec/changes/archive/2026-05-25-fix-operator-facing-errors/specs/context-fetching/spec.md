## MODIFIED Requirements

### Requirement: Context window overflow handling

When the assembled prompt's estimated input size exceeds the active model's context window (with a 20 percent safety margin), the reviewer SHALL fail the run with an actionable error message and exit non zero. Fetched file content MUST NOT be silently truncated or selectively dropped to fit. Estimation MAY use a character heuristic for v1. The actionable error message MUST name only environment variables that exist in `Config`; references to env vars that have never been defined are forbidden.

#### Scenario: Overflow detected before API call
- **WHEN** the assembled `system_prompt + user_prompt` is estimated to exceed the active model's context window
- **THEN** the placeholder comment is updated with the message "context too large: disable AI_FETCH_CHANGED_FULL, lower AI_FETCH_RELATED_DEPTH, or reduce the PR scope" and the process exits 1

#### Scenario: Prompt under the limit proceeds normally
- **WHEN** the estimated size is within the model's context window minus the safety margin
- **THEN** the reviewer proceeds with the API call, posts the review, and runs the gatekeeper as usual

#### Scenario: Error message names a real env var
- **WHEN** the overflow path is triggered
- **THEN** the raised error's text contains the literal string `AI_FETCH_CHANGED_FULL` (the actual configuration variable) and does NOT contain `AI_FETCH_FULL_FILES` (which has never existed)
