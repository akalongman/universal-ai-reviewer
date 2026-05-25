## ADDED Requirements

### Requirement: Structured severity directive in AI response

The system prompt SHALL instruct the model to begin every response with a single structured directive line in HTML comment form. The directive is the only authoritative signal of severity for CI purposes; the rendered markdown body that follows is informational only.

The directive format MUST be exactly:

```
<!-- ai-review: critical=N; suggestions=N; nitpicks=N -->
```

where each `N` is a non-negative integer. The keys `critical`, `suggestions`, `nitpicks` MUST all be present. Additional keys MAY be ignored by the parser. The directive MUST occupy the first non-whitespace line of the response.

The system prompt MUST also tell the model that the legacy category headers (`🔴 Critical Issues`, `🟡 Suggestions`, `🟢 Nitpicks/Praise`) are retained for human readability but are no longer the gatekeeper's signal source.

#### Scenario: Model emits directive with zero critical
- **WHEN** the model finds no critical issues
- **THEN** its response begins with `<!-- ai-review: critical=0; suggestions=N; nitpicks=N -->` followed by the markdown body
- **AND** the markdown body MAY freely omit, include, or describe issues of any severity; the gatekeeper does not read it

#### Scenario: Model emits directive with non-zero critical
- **WHEN** the model finds one or more critical issues
- **THEN** its response begins with `<!-- ai-review: critical=N; suggestions=N; nitpicks=N -->` where N is the count of critical findings
- **AND** the body SHOULD contain a `🔴 Critical Issues` section enumerating them for the human reviewer

#### Scenario: System prompt explains directive is load-bearing
- **WHEN** any response is generated
- **THEN** the system prompt that produced it contained explicit text instructing the model that the directive line determines CI pass/fail and that the markdown body does not
