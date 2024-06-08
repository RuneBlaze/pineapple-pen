fix:
    ruff check --exit-zero --fix .
    ruff format .

clear:
    rm -r .cache

streamlit:
    poetry run streamlit run src/genio/game.py