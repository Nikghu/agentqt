Analyze the current conversation transcript to find PyQt6-related behaviors worth preventing with hooks, then implement approved rules in settings.json.

**Periodic maintenance only — do not invoke during normal development tasks.**

$ARGUMENTS

## Step 1 — Scan the Transcript

Read the conversation history and look for these patterns:

### Explicit Corrections
- "No, don't do that" / "Stop doing X" / "I said NOT to..."
- "That's wrong, use Y instead"

### Frustrated Reactions
- User reverting changes Claude made
- Repeated "no" or "wrong" responses
- User manually fixing Claude's output
- Escalating frustration in tone

### Repeated Issues
- Same mistake appearing multiple times
- Claude repeatedly using a tool in an undesired way
- Patterns the user keeps correcting

### Reverted Changes
- `git checkout -- file` or `git restore file` after Claude's edit
- User undoing or re-editing files Claude just touched

---

## Step 2 — Produce Findings

For each identified behavior output a block:

```yaml
behavior: "Description of what Claude did wrong"
frequency: "How often it occurred"
severity: high|medium|low
suggested_rule:
  name: "descriptive-rule-name"
  event: bash|file|stop|prompt
  pattern: "regex pattern to match"
  action: block|warn
  message: "What to show when triggered"
```

Prioritize high-frequency, high-severity behaviors first.

---

## Step 3 — Implement Approved Rules

For each rule the user approves:
1. Read `.claude/settings.json` (never overwrite — merge only)
2. Add the hook using the appropriate event type
3. Pipe-test the command before writing
4. Validate JSON after writing
5. Report what was added and which file was changed

Use the `update-config` skill for guidance on hook structure if needed.
