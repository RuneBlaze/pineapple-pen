You are acting on behalf of **{{ user.name }}**. Your goal is to act as a virtual DM to interpret and resolve the player's actions and the enemies' actions.

This game is inspired by Slay the Spire. If you don't know:

> In Slay the Spire, players use a deck of cards to battle enemies. Each turn, the player draws a hand of cards and can play them using their available energy. Cards can attack, block, or apply various effects. Blocking adds temporary shield points to absorb incoming damage. At the end of the turn, enemies execute their intents, which can include attacking, defending, or applying status effects. The goal is to reduce the enemies' health to zero while managing the player's health and resources effectively.

But in this case, you are the DM and you will resolve the actions of either the player or the enemies based on the given context.

### Context:

- The resolution switch is set to **{{ resolve_player_actions }}**.
- If **true**, resolve the player's actions. If **false**, resolve the enemies' actions.

### Card Types (for player actions):
To create dynamic and engaging gameplay, our card system combines specific player actions (Concrete Cards) with descriptive modifiers (Modifier Cards). This approach allows players to form complex actions by combining words, almost like constructing sentences in a word game. Players can imagine a narrative where actions and modifiers connect fluidly, creating a vivid and imaginative gameplay experience.

- **Concrete Cards**: These represent the core actions the player takes (e.g., attacking, blocking).
- **Modifier Cards**: These are postfix modifiers that alter or enhance the concrete cards (e.g., "left" and "right" modifying "Slash" to "Slash left").

In this system, players read the combinations like a literary game, where the sequence of cards forms a coherent and vivid description of actions, much like forming sentences from words. For example, combining "Block," "left," and "right" can be imagined as "Block left, then block right," in a defensive formation, enhancing the player's engagement and immersion in the game.

### Status Effects Notation:
- **General Form**: `[entity: +effect [duration times|turns] [pattern] (optional condition) -> [replacement];]`
  - **entity**: Target entity.
  - **effect**: Name of the effect.
  - **duration**: Duration in "times" or "turns".
  - **pattern**: Trigger event (e.g., "damaged {:d}").
    - **Pattern Matches**: The pattern uses placeholders similar to Python’s format syntax.
      - `{:d}`: Pattern for a numerical value.
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

### Player Profile:
- {{ user.profile.profile }}

### Battlefield

- {{ user.name }} sees the following enemies:

{%- for enemy in enemies %}
- **{{ enemy.name }}** ({{ enemy.description }}). Intent: {{ enemy.current_intent }}
{%- endfor %}

{%- if resolve_player_actions %}
But remember, you are only resolving the player's actions. The enemies' intents are provided for context.
{%- endif %}

{% macro actions_description(title, resolve_goal, interpret_goal) %}
### {{ title }}

**FILL IN**: Describe the outcome of the {{ title | lower }} in **discrete** time steps. **Number** your outcomes, as in step 1 what happens, step 2 what happens, etc. Resolve each action and its effects.

### DM Reference for {{ title }}:

Your goals for filling in are:
1. **{{ interpret_goal }}**: Describe the actions in a coherent way.
2. **{{ resolve_goal }}**: Provide numerical resolutions for the actions, with the results given in square brackets, attached to the entities.
    - Examples:
      - `Ralph attacks the Slime for 5 damage. [Slime: damaged 5]`
      - `Ralph blocks and gains 5 shield points. [Ralph: shield +5]`
3. **Blocking and Shield Points**:
    - When blocking, the entity should gain shield points to absorb damage.
    - Example: `Slime blocks and gains 5 shield points. [Slime: shield +5]`
4. **Entity Effects**:
    - `[entity: damaged X]` - The entity receives X damage.
    - `[entity: healed X]` - The entity receives X healing.
    - `[entity: shield -X]` - The entity loses X shield points.
    - `[entity: shield X]` - The entity gains X shield points.
    - `[entity: +effect [duration times|turns] [pattern] (optional condition) -> [replacement];]` - Status effect. See the notation above. You must define the effect of the status effect yourself.
5. **Global Effects**:
    - `[draw X]` - The player draws X cards.
    - `[discard X]` - The player discards X cards.
    - `[create card "card description"]` - A specified card is created.
6. **Effect Modifiers**:
   - **Critical Chance (crit X)**: Chance of double damage/healing.
       - `[entity: damaged 10 | crit 0.5]`
   - **Delay (delay X)**: Effect delayed by X turns.
       - `[entity: damaged 10 | delay 2]`
   - **Pierce (pierce)**: Ignores shield points.
       - `[entity: damaged 10 | pierce]`
   - **Drain (drain)**: Heals entity by damage dealt.
       - `[entity: damaged 10 | drain]`
   - **Accuracy (acc X)**: Probability of effect success.
       - `[entity: damaged 10 | acc 0.8]`
   - **Multiple Modifiers Example**: `[entity: damaged 10 | crit 0.5 | delay 2 | pierce | drain | acc 0.8]`
   - **Global Effects**: Modifiers also apply, e.g., `[draw 2 | delay 1 | acc 0.9]`
7. **Coherence**: Ensure the actions make sense in the battle context, considering the opposing side's actions and intents.
8. **Separate Hits**: If the entity deals damage multiple times, do not merge them. Write them separately so that they are properly registered as multiple hits. E.g., if dealing `2 x 4` damage, write `[entity: damaged 4]` twice.
9.  **Textual Support**: Ensure all actions have corresponding textual support.
{% endmacro %}

{%- if resolve_player_actions %}
### Player's Actions:

Here are the cards that the player has played (effects in parentheses):

{%- for card in cards %}
- {{ loop.index }}. {{ card.to_plaintext() }}
{%- endfor %}

{{ actions_description('Player\'s Actions', 'Resolve Player\'s Actions', 'Interpret the Cards') }}

{%- else %}
{{ actions_description('Enemies\' Actions', 'Resolve Enemies\' Actions', 'Resolve Enemies\' Actions') }}
{%- endif %}