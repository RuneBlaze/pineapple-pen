# API Docs

## Global Functions

### Essential Functions

```python
prob_check(prob: float) -> bool # Returns True if a random number between 0 and 1 is less than prob.
battler(search_term: str) -> Battler # Returns a Battler object with the name closest to search_term.
log(message: str) -> None # Logs a message to the console.
repaint(board: str, legends: dict[str, str] = {}) -> None # Changes the board to the specified board. The DM is responsible for defining the board and handling movement. See `repaint` section for more details.
```

### Helper functions

```python
active_battler() -> Battler # Returns the battler whose turn it is.
```

### More on `repaint`

As a DM, often it is necessary to update the board to reflect the current state of the game, e.g., due to knockback, terrain effects,
traps, etc.. It is like marking the map with a pen.

#### Example 1

```python
# For example, this is the initial board.
initial_board = """\
...
Aa.
...
"""

# Say if the battler of `A` successfully knocks back the battler of `a`, then the board should be updated to:

repaint("""\
...
A.a
...
""")
```

#### Example 2

Say that some terrain effect as been applied. Or as the DM you want to change the board to reflect the current state of the game
in any way you want. Feel free to "draw" the board as you like.

```python
repaint("""\
.^.
^A^
.^.
""", {"^": "Trap set by Ralph, deals 10 damage to whoever steps on it."})
```

## `Battler`

### Properties

Given `battler: Battler`, `battler.patk` refers to the physical attack power of the battler, and so on. We have more properties:

#### Status

- **patk**: Physical attack power
- **pdef**: Physical defense power
- **matk**: Magical attack power
- **mdef**: Magical defense power
- **agi**: Agility
- **eva**: Evasion rate
- **hp**: Current health points (HP)
- **mp**: Current magical points (MP)
- **mhp**: Maximum HP
- **mmp**: Maximum MP

#### Others

 - **name**: The name of the battler, e.g. "Ralph" or "Slime 1"

### Methods

#### Basic Methods

```python
battler.receive_damage(damage: int) -> None
battler.receive_heal(heal: int) -> None
```

#### Status Effects

Status effects are implemented via the `mark` method, where a specific status effect (with a name)
and a list of (natural-language described) effects are applied to the battler for a certain number of turns.

```python
battler.mark(status_name: str, effects: list[str], duration_turns: int) -> None
```

For example, a poison effect can be applied as follows:

```python
# Example
battler.mark("poison", ["Lose 10% of HP each after each turn"], 3)
```

And the effects system is responsible to interpret the effects and apply them to the battler
(via the `receive_damage` method).

# API by Example

## Normal Attack

> Suppose that Ralph uses a "normal attack" on Slime 1, and the attack has an 80% chance of hitting.
> In addition, the damage formula is `2 * attacker.patk - defender.pdef`, and this attack deals one knockback when hit.

```python
ralph = battler("ralph")
slime = battler("slime 1")

if prob_check(0.8):
    slime.receive_damage(2 * ralph.patk - slime.pdef)
    repaint(...) # Board updated to reflect the knockback, omitted for brevity.
else:
    log("Ralph missed the attack!")
```

## Poison Attack

> Suppose that Slime 1 uses a "poison attack" on Ralph, and the attack has a 100% chance of hitting, with
> very minor damage (`1 * attacker.patk - defender.pdef`), and has no knockback.
> In addition, the attack has a 50% chance of poisoning Ralph for 3 turns, where Ralph loses 10% of his HP each turn.

```python
ralph = battler("ralph")
slime = battler("slime 1")

if prob_check(1.0):
    damage = 1 * slime.patk - ralph.pdef
    ralph.receive_damage(damage)
    ralph.mark("poison", ["Lose 10% of HP each after each turn"], 3)
else:
    log("Slime missed the attack!")
```

## Complicated Scenario

> Suppose that Bennett, an archer, shoots an arrow at Slime 1, and Bennett currently has an active mark of "poison",
> which causes him to lose 10% of his HP each turn, but Slime 1 is blocked by Goblin 1.
> In addition, the goblin has a mark on it that buffs its defense by 50%.
> Suppose that you, as the DM, want to simulate that Goblin 1 *might* block the attack. It might look something like this:

```python
bennett = battler("bennett")
slime = battler("slime 1")
goblin = battler("goblin 1")

if prob_check(0.5):
    # Did not hit the goblin
    if prob_check(0.8):
        slime.receive_damage(2 * bennett.patk - slime.pdef)
    else:
        log("Bennett missed the attack!")
else:
    # Hit the goblin
    log("Due to the goblin standing in the way, Bennett's attack is more like shooting an arrow at the goblin!")
    if prob_check(0.8):
        goblin.receive_damage(2 * bennett.patk - goblin.pdef * (1 + 0.5))
    else:
        log("The goblin was trying to block the attack, and Bennett missed the attack!")

# In any case, Bennett loses 10% of his HP due to poison
bennett.receive_damage(bennett.mhp // 10)
log("Bennett loses 10% of his HP due to poison!")
```