def parse_judgement_output(output):
    # Split the output by lines
    lines = output.strip().split("\n")

    # Initialize variables to hold the Python program and the board
    python_program = []
    board = []

    # Flags to indicate which part we are parsing
    in_python_program = False
    in_board = False

    # Iterate through each line and categorize it
    for line in lines:
        if line.strip() == "```python":
            in_python_program = True
            in_board = False
            continue
        elif line.strip() == "```board":
            in_board = True
            in_python_program = False
            continue
        elif line.strip() == "```":
            in_python_program = False
            in_board = False
            continue

        if in_python_program:
            python_program.append(line)
        elif in_board:
            board.append(line)

    # Join the lines to form the final strings
    python_program_str = "\n".join(python_program)
    board_str = "\n".join(board)

    return python_program_str, board_str


if __name__ == "__main__":
    output = """
```python
ralph = battler("ralph")
slime1 = battler("slime 1")

slime1.receive_damage(ralph.atk - slime1.pdef * 2)
```

Also fill out a new board. Mark the new board with the board tag:

```board
# NEW BOARD
```
"""
    print(parse_judgement_output(output))
