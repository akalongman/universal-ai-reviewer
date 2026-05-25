## 1. Spec correction

- [x] 1.1 Update `openspec/specs/context-fetching/spec.md` "Context window overflow handling" → "Overflow detected before API call" scenario to reference `AI_FETCH_CHANGED_FULL` instead of `AI_FETCH_FULL_FILES`
- [x] 1.2 Apply the same correction in this change's spec delta under `specs/context-fetching/spec.md`

## 2. Implementation fixes

- [x] 2.1 `reviewer/context_fetcher.py`: rename `AI_FETCH_FULL_FILES` to `AI_FETCH_CHANGED_FULL` in the `ContextTooLargeError` message
- [x] 2.2 `action.yaml`: declare `openai_api_key` as a top-level input (description, `required: false`, no default)
- [x] 2.3 `reviewer/llm_providers.py`: in `OpenAIReviewer.review`, replace `max_tokens` with `max_completion_tokens` in the `kwargs` dict passed to `client.chat.completions.create`

## 3. Tests

- [x] 3.1 `tests/test_context_fetcher.py`: add `test_overflow_error_names_real_env_var` asserting the raised `ContextTooLargeError`'s message contains `AI_FETCH_CHANGED_FULL` and does not contain `AI_FETCH_FULL_FILES`
- [x] 3.2 `tests/test_providers.py`: update `test_openai_reviewer_stream_parsing` to assert `call_kwargs['max_completion_tokens']` instead of `call_kwargs['max_tokens']`

## 4. Verification

- [x] 4.1 `python -m pytest tests/ -v` passes from the repo root
- [x] 4.2 The overflow error message, when triggered manually, names a variable that actually exists in `Config`
