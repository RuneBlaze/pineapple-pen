## Status Effects:

### Status Effect Notations

Sometimes status effects like `vulnerable` or `poisoned` are applied to entities. Here is the notation for status effects:

- **General Form**: `[entity: +effect [duration times|turns] [pattern] (optional condition) -> [replacement];]`
  - **entity**: Target entity.
  - **effect**: Name of the effect.
  - **duration**: Duration in "times" or "turns".
  - **pattern**: Trigger event (e.g., "damaged {:d}").
    - **Pattern Matches**: The pattern uses placeholders similar to Python’s format syntax.
      - `{:d}`: Pattern for a numerical value. `{}`: Generic pattern.
      - `m[0]`: First match, `m[1]`: Second match, etc.
  - **optional condition**: Condition for the effect.
    - **Syntax**: `(if condition)`
      - **condition**: Logical statement that must be true for the effect to trigger.
  - **replacement**: Action when the pattern matches.

### Examples:
1. **Frail**: Reduces block gain by 25% for 3 turns.
  - Notation: {% raw %}`[entity: +frail [3 turns] [ME: block {:b}] -> [ME: block {{m[0] * 0.75}}];]`{% endraw %}. `ME` is a special form that will always be replaced by the entity's name.
2. **Intangible**: Reduces all damage to 1 for 1 turn.
  - Notation: `[entity: +intangible [1 turn] [ME: damaged {:d}] -> [ME: damaged 1];]`
3. **Burn**: Deals 2 damage at end of turn for 3 turns.
  - Notation: `[entity: +burn [3 turns] [ME: end of turn] -> [ME: damaged 2];]`
4. **Diamond Shield**: Cancels damage <= 2 for 2 times.
  - Notation: {% raw %}`[entity: +diamond shield [2 times] [ME: damaged {:d}] (if m[0] <= 2) -> [ME: damaged {{0}}];]`{% endraw %}

Anything instant should not require a status effect.