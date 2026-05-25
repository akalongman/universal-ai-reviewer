## 0. Design decisions (must be resolved before any code is written)

- [ ] 0.1 Confirm directive format: HTML comment `<!-- ai-review: critical=N; suggestions=N; nitpicks=N -->` vs. JSON code block vs. YAML frontmatter
- [ ] 0.2 Confirm position: first line vs. last line vs. anywhere
- [ ] 0.3 Confirm backward-compat policy: dual-read in 1.x with prose fallback, hard-cut at 2.0
- [ ] 0.4 Confirm conflict policy: directive wins, log warning on disagreement

## 1. System prompt update

- [ ] 1.1 Add directive instruction to `prompts.build_prompts` system context. The instruction MUST specify exact format, position, and that this is the only authoritative gatekeeper signal
- [ ] 1.2 Preserve existing category-header guidance (`🔴`, `🟡`, `🟢`) for human readability, but explicitly tell the model the gatekeeper no longer reads these headers
- [ ] 1.3 Update the "If flawless" example response to include the directive (e.g. `<!-- ai-review: critical=0; suggestions=0; nitpicks=0 -->\n### Looks good to me!`)

## 2. Parser

- [ ] 2.1 Implement `parse_severity_directive(review_text: str) -> dict | None` in `reviewer/prompts.py` (or new `reviewer/gatekeeper.py` if it grows)
- [ ] 2.2 Parser MUST return `None` when no directive is present (signals "fall back to legacy prose parsing")
- [ ] 2.3 Parser MUST raise `DirectiveParseError` on malformed directive (signals "fail-closed, this is suspicious")
- [ ] 2.4 Parser tests: valid directive, missing keys default to 0, extra keys ignored, malformed value, multiple directives (last wins or error — decision needed)

## 3. Gatekeeper rewrite

- [ ] 3.1 In `reviewer/main.py`, restructure the gatekeeper block: try `parse_severity_directive` first
- [ ] 3.2 If directive present: `critical_count > 0` → exit 1, else exit 0. Log a one-line summary of all counters
- [ ] 3.3 If directive absent and `critical_section_is_empty` says empty → exit 0 with `DEPRECATION: AI response did not include severity directive; falling back to prose parsing`
- [ ] 3.4 If directive absent and prose parsing says non-empty → exit 1 (current behaviour)
- [ ] 3.5 If directive says 0 but body contains `🔴 Critical Issues` header → log warning, trust the directive, exit 0

## 4. Tests

- [ ] 4.1 Parametrized tests for the parser covering each valid form and each malformed form
- [ ] 4.2 Tests for the gatekeeper logic: directive present + 0/non-zero, directive absent + fallback (each branch), conflicting directive + body
- [ ] 4.3 Confirm existing `critical_section_is_empty` tests still pass (the function lives on as the fallback)

## 5. Documentation

- [ ] 5.1 README: add a "How the gatekeeper decides" section explaining the directive, its format, and the dual-read window
- [ ] 5.2 README: add troubleshooting note for `DEPRECATION` log line and what to do about it
- [ ] 5.3 CLAUDE.md: add the new capability to the capability-spec table if one is created, or note the structured directive contract inline if not

## 6. Verification

- [ ] 6.1 `python -m pytest tests/ -v` passes from the repo root
- [ ] 6.2 Manual run: synthesise a `mr_diff.txt`, run `python reviewer/main.py` with mocked AI client returning a directive-prefixed response, confirm gatekeeper exits 0
- [ ] 6.3 Manual run: same setup with `critical=1` in the directive, confirm exit 1
- [ ] 6.4 Manual run: response without directive but with negation body, confirm exit 0 + DEPRECATION log line
