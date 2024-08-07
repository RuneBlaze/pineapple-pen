### Rulebook for "Pen Apple"

#### Overview
"Pen Apple" is a card game inspired by "Slay the Spire," where players use a deck of cards to battle enemies. Each turn, players draw a hand of cards and can play them using their available energy. Cards can attack, block, or apply various effects. Blocking adds temporary shield points to absorb incoming damage. The objective is to reduce the enemies' health to zero while managing the player's health and resources effectively.

#### Card Types
- **Concrete Cards**: These cards have well-defined descriptions, forming the core of an action or series of actions.
- **Modifier Cards**: These cards act as postfix modifiers, providing additional context or modifying the concrete cards.

#### Examples of Cards
1. **Concrete Card**: 
   - **Name**: Shield Bash
   - **Description**: Deal 8 damage. Gain 5 shield points.
2. **Concrete Card**: 
   - **Name**: Healing Touch
   - **Description**: Heal for 10 health.
3. **Modifier Card**: 
   - **Name**: Swiftly
   - **Description**: Increases the effect's speed, making it more likely to go first.
4. **Modifier Card**: 
   - **Name**: Brutally
   - **Description**: Increases the damage dealt by 50%.

#### Battlefield
- The battlefield consists of the player's profile and visible enemies with defined intents.
- The resolution switch determines whether player or enemy actions are resolved:
  - **True**: Resolve player's actions.
  - **False**: Resolve enemies' actions.

#### Actions and Effects
- **Blocking and Shield Points**:
  - Entities gain shield points to absorb damage when blocking.
  - Example: Entity blocks and gains 5 shield points.

- **Entity Effects**:
  - Entities can receive damage, healing, gain, or lose shield points.
  - Example: Entity receives 10 damage. Entity heals for 10 health.

- **Effect Modifiers**:
  - **Critical Chance**: Chance of double damage or healing.
  - **Delay**: Effect delayed by a certain number of turns.
  - **Pierce**: Ignores shield points.
  - **Drain**: Heals the entity by the damage dealt.
  - **Accuracy**: Probability of effect success.

#### Status Effects

These are only examples -- you can create your own status effects as needed.

- **Frail**: Reduces block gain by 25% for 3 turns.
- **Intangible**: Reduces all damage to 1 for 1 turn.
- **Burn**: Deals 2 damage at the end of the turn for 3 turns.
- **Diamond Shield**: Cancels damage less than or equal to 2 for 2 times.

#### Resolving Actions
- Actions are resolved in discrete time steps with clear outcomes.
  - Example: Ralph attacks the Slime for 5 damage.
  - Example: Ralph blocks and gains 5 shield points.
- Ensure coherence and logical consistency in the context of the battle.
- Write separate hits for multiple damage instances.
- Provide textual support for all actions.

#### Example Gameplay Scenarios
- **Scenario 1**: The player plays the cards "Shield Bash" and "Swiftly".
  - **Outcome**: The player deals 8 damage and gains 5 shield points quickly, making it more likely to go first.
  
- **Scenario 2**: The player plays the cards "Healing Touch" and "Brutally".
  - **Outcome**: The player heals for 15 health (10 base healing + 50% increase from Brutally).

### Instructions for Game Designers

1. **Designing Cards**:
   - Create a mix of concrete and modifier cards to allow for dynamic and engaging gameplay.
   - Ensure concrete cards have clear and well-defined actions.
   - Modifier cards should provide flexibility and additional context to the actions.

2. **Creating the Battlefield**:
   - Define the player's profile and visible enemies with their intents.
   - Use the resolution switch to determine whether player or enemy actions are being resolved.

3. **Resolving Actions**:
   - Follow the rules for blocking, entity effects, and modifiers.
   - Apply status effects as described, ensuring they align with the intended gameplay mechanics.
   - Resolve actions in discrete steps, maintaining coherence and logical consistency.

4. **Playtesting**:
   - Regularly test the game to ensure balance and fun.
   - Make adjustments to card effects, status effects, and gameplay mechanics based on feedback and observations.

By following these guidelines, you can create a compelling and enjoyable experience for players in "Pen Apple".