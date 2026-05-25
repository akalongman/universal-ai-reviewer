## ADDED Requirements

### Requirement: Directive-first gatekeeper decision

The gatekeeper SHALL prefer the structured severity directive over prose parsing when deciding pass/fail. Parsing precedence:

1. If a valid `<!-- ai-review: ... -->` directive is present in the AI response, the gatekeeper SHALL use its `critical` value. `critical > 0` → exit 1. `critical == 0` → exit 0.
2. If no directive is present, the gatekeeper SHALL fall back to the legacy prose-parsing path (`critical_section_is_empty`) and log a one-line `DEPRECATION` notice naming the model and the run.
3. If a directive is present but malformed (missing keys, non-integer values), the gatekeeper SHALL fail-closed: exit 1 with an error message pointing at the offending line. Malformed directives are not retried via the prose fallback because they signal model drift on a load-bearing instruction.

The exit code contract is preserved verbatim: 0 = no critical issues, 1 = critical issues found OR malformed response. No new exit codes are introduced.

#### Scenario: Directive says zero, body is empty
- **WHEN** the response is `<!-- ai-review: critical=0; suggestions=0; nitpicks=0 -->\n### Looks good to me!`
- **THEN** the gatekeeper exits 0

#### Scenario: Directive says one or more critical
- **WHEN** the response is `<!-- ai-review: critical=2; suggestions=0; nitpicks=0 -->\n### 🔴 Critical Issues\n- ...`
- **THEN** the gatekeeper exits 1

#### Scenario: Directive absent, body indicates empty
- **WHEN** the response has no directive line but its critical section is a recognised negation (per the legacy `critical_section_is_empty` heuristic)
- **THEN** the gatekeeper exits 0 AND logs `DEPRECATION: AI response did not include severity directive; falling back to prose parsing. Please upgrade the system prompt.`

#### Scenario: Directive absent, body indicates findings
- **WHEN** the response has no directive line and its critical section contains findings
- **THEN** the gatekeeper exits 1 (same as legacy behaviour) AND logs the same DEPRECATION line

#### Scenario: Directive malformed
- **WHEN** the response begins with `<!-- ai-review: critical=oops -->` or omits required keys
- **THEN** the gatekeeper exits 1 AND logs `ERROR: AI response contained a malformed severity directive: <line>. Treating as critical-issues-detected.`

#### Scenario: Directive conflicts with body
- **WHEN** the directive says `critical=0` but the body contains a `🔴 Critical Issues` header
- **THEN** the gatekeeper trusts the directive (exits 0) AND logs `WARNING: directive says critical=0 but body contains a critical-issues header; trusting the directive.`
