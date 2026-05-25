## Why

A project review surfaced a small cluster of bugs that all share one property: they silently mislead the *operator* of the reviewer (the CI engineer who configures it) rather than the model. The most damaging single example is the `ContextTooLargeError` message in `reviewer/context_fetcher.py`, which tells the operator to disable a variable called `AI_FETCH_FULL_FILES`. No such variable exists in `Config`. The real variable is `AI_FETCH_CHANGED_FULL`. An operator who hits the overflow follows the advice, sees no change, follows the advice again, and either retries indefinitely or assumes the tool is broken.

This typo also appears verbatim in the `context-fetching` specification (`openspec/specs/context-fetching/spec.md`, Scenario "Overflow detected before API call"), so any future re-implementation that derived its error string from the spec would reproduce the bug. Fixing the code alone is not enough; the spec text must change in the same proposal so the contract and the implementation stop disagreeing.

Two other operator-facing fixes ride along in the same change because they sit at the same boundary ("what the operator sees when something goes wrong") and have negligible additional risk:

- `action.yaml` references `inputs.openai_api_key` from its `env:` block but never declares that input. The composite-action resolver returns the empty string for undeclared inputs without warning, so every GitHub consumer of the OpenAI path runs with `OPENAI_API_KEY=""` and gets a misleading "missing API key" message from `Config._validate`. No spec change; pure wiring fix.
- `reviewer/llm_providers.py` passes `max_tokens` to OpenAI chat completions. OpenAI deprecated this parameter in November 2024 in favor of `max_completion_tokens`; reasoning models (`o1`, `o3`, and reasoning-mode `gpt-5` variants) hard-reject the legacy name with HTTP 400. The README already exposes `AI_MODEL` as a free-form string and recommends OpenAI in the quick-start, so consumers can and will set a reasoning model and see a 400. No spec change (the spec is silent on provider parameter names); implementation fix only.

## What Changes

- **MODIFIED**: the `context-fetching` capability's "Context window overflow handling" requirement. The scenario text now references `AI_FETCH_CHANGED_FULL` (the real variable) instead of `AI_FETCH_FULL_FILES` (the fictional one).
- **FIX**: `reviewer/context_fetcher.py` `ContextTooLargeError` message string updated to match the corrected scenario.
- **FIX**: `action.yaml` declares `openai_api_key` as an input.
- **FIX**: `reviewer/llm_providers.py` `OpenAIReviewer.review` sends `max_completion_tokens` instead of the deprecated `max_tokens`. Existing OpenAI provider test updated to assert the new parameter name.
- **TEST**: new regression test that the overflow error message names the actual env var, so a future copy-paste regression fails CI immediately.

## Capabilities

### Modified Capabilities
- `context-fetching`: corrects the env var name in the overflow scenario. No requirement is added or removed; only the scenario's literal env var string changes. Behaviour requirement is unchanged.

### Unaffected Capabilities
- `pipeline-orchestration`, `prompt-engineering`, `diff-handling`, `vcs-integration`, `configuration`: untouched by this change.
- `llm-integration` and `ci-runners`: code changes only, no spec text. The `llm-integration` streaming contract (concatenate chunks into a single markdown blob) is preserved verbatim. The `ci-runners` wiring fix adds one declared input but does not change runtime behaviour for any consumer who was already passing `openai_api_key` as a `with:` arg.

## Impact

### Code

- `reviewer/context_fetcher.py`: one-line error message change.
- `reviewer/llm_providers.py`: one-line parameter rename in the OpenAI path.
- `action.yaml`: three lines added to the `inputs:` block.
- `tests/test_providers.py`: assert `max_completion_tokens` instead of `max_tokens` in the OpenAI test.
- `tests/test_context_fetcher.py`: new test confirming the overflow error message contains `AI_FETCH_CHANGED_FULL`.

### Cross-capability impact

None. The category header contract between `prompt-engineering` and `pipeline-orchestration` is untouched. The VCS provider contract is untouched. The diff handling pipeline is untouched.

### Backward compatibility

- The error message change is a string-only fix. Any tool grepping logs for the literal `AI_FETCH_FULL_FILES` would have been grepping for a string that never resolved to anything actionable; this change cannot regress them.
- The `action.yaml` input addition is additive (new optional input). Existing workflows that already pass `openai_api_key` start working; existing workflows that do not pass it continue not to (no behaviour change for non-OpenAI users).
- The OpenAI parameter rename is a behavioural change but matches the SDK's current contract. Consumers on legacy `gpt-3.5-turbo` may want to verify the response cap still applies (it does; OpenAI honours both names on legacy models but emits a deprecation warning for the legacy one).

### Rollback

Trivial. Revert the change. Operators who were not yet using the OpenAI path see no difference; operators on reasoning models who were hitting the 400 keep hitting it.
