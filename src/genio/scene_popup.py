import pyxel
from genio.scene import Scene
from genio.components import Popup

class ScenePopup(Scene):

    def __init__(self) -> None:
        self.timer = 0
        self.popups = []
    
    def update(self) -> None:
        self.timer += 1

        if self.timer % 30 == 0:
            self.popups.append(Popup("Vulnerable", 120, 60, 7))

        for popup in self.popups:
            popup.update()

        self.popups = [popup for popup in self.popups if not popup.is_dead()]
    
    def draw(self) -> None:
        pyxel.cls(0)
        for popup in self.popups:
            popup.draw()

def gen_scene() -> Scene:
    return ScenePopup()