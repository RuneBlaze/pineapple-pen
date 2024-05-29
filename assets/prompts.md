Respond in the form of "judgements", in the form of a Python program,
deciding the outcome of the following action:

> Ralph uses the skill "Burst Trio" on "Slime 1".
> Burst Trio:
>    1. A skill of the utmost power, capable of destroying even the most powerful of foes.
>    2. Damage formula: 3 * Attacker.patk - 2 * Defender.pdef
>    3. Accuracy: 100%
>    4. This skill deals 50% blast damage to surrounding enemies.

Fill out the following Python function as your judgement:

```python
ralph = battler("ralph")
slime1 = battler("slime 1")

slime1.receive_damage(ralph.atk - slime1.pdef * 2)
```

Also fill out a new board. Mark the new board with the board tag:

```board
# NEW BOARD
```

Omit all type annotations in your output to save space. Return a single Python code-block with a program that decides the outcome of the action, and a new board.