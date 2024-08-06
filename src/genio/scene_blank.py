import pyxel

from genio.scene import Scene, module_scene


@module_scene
class SceneBlank(Scene):
    def __init__(self) -> None:
        super().__init__()

    def draw(self) -> None:
        pyxel.cls(0)

    def update(self) -> None:
        ...
