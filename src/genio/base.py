import os

WORKING_DIR = os.getcwd()

WINDOW_WIDTH, WINDOW_HEIGHT = 427, 240


def asset_path(*args: str):
    return os.path.join(WORKING_DIR, "assets", *args)
