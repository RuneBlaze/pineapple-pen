fix:
    ruff check --exit-zero --fix .
    ruff format .

clear:
    rm -r .cache

edit:
    poetry run pyxel edit assets/sprites.pyxres

play:
    poetry run python -m genio.main

ps:
    poetry run python -m genio.main --edit