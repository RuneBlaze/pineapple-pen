fix:
    ruff check --exit-zero --fix .
    ruff format .

clear:
    rm -r .cache

streamlit:
    poetry run streamlit run src/genio/game.py

edit:
    poetry run pyxel edit assets/sprites.pyxres

play:
    poetry run python -m genio.main