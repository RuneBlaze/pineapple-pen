from itertools import cycle

import pyxel

from genio.base import WINDOW_HEIGHT, WINDOW_WIDTH
from genio.predef import access_predef, refresh_predef
from genio.ps import Anim
from genio.scene import Scene


class Peekable:
    def __init__(self, iterable):
        self.iterator = iter(iterable)
        self._next = next(self.iterator, None)

    def __iter__(self):
        return self

    def __next__(self):
        if self._next is None:
            raise StopIteration
        result = self._next
        self._next = next(self.iterator, None)
        return result

    def peek(self):
        return self._next


class ParticleDemoScene(Scene):
    def __init__(self):
        self.particle_configs = Peekable(cycle(access_predef("anims").items()))
        self.anims = []
        self.timer = 0

    def update(self):
        if pyxel.btnp(pyxel.KEY_SPACE):
            refresh_predef()
            self.particle_configs = Peekable(cycle(access_predef("anims").items()))
        if pyxel.btnp(pyxel.KEY_Q):
            next(self.particle_configs)
        for anim in self.anims:
            anim.update()
        self.anims = [anim for anim in self.anims if not anim.dead]

        if self.timer % 30 == 0 and not self.anims:
            self.add_anim(
                self.particle_configs.peek()[1], WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
            )
        self.timer += 1

    def add_anim(self, name: str, x: int, y: int, play_speed: float = 1.0):
        self.anims.append(Anim.from_predef(name, x, y, play_speed))

    def draw(self):
        pyxel.cls(0)
        pyxel.text(0, 0, "Press Q to change particle config", 7)
        pyxel.text(0, 10, f"Current: {self.particle_configs.peek()[0]}", 7)
        pyxel.text(0, 20, "Press SPACE to reload", 7)
        for anim in self.anims:
            anim.draw()


def gen_scene():
    return ParticleDemoScene()
