from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pyxel
from lupa.lua54 import LuaRuntime

from genio.predef import access_predef


@dataclass
class EmitterConfig:
    frequency: int
    max_p: int
    size: tuple[int, int, int, int] | int
    speed: int
    life: float | list[float]
    colors: list[int] | None
    sprites: list[int] | None
    area: tuple[int, int] | None
    burst: tuple[bool, int] | None
    angle: list[int | float] | None = None
    gravity: bool = False
    duration: float | None = None


def convert_to_emitter_configs(parsed_data: list) -> list[EmitterConfig]:
    emitter_configs = []

    for item in parsed_data:
        config = EmitterConfig(
            frequency=item["frequency"],
            max_p=item["max_p"],
            size=tuple(item["size"])
            if isinstance(item["size"], list)
            else item["size"],
            speed=item["speed"],
            life=item["life"],
            colors=item["colors"] if "colors" in item else None,
            area=tuple(item["area"]) if "area" in item else None,
            burst=(item["burst"][0], item["burst"][1]) if "burst" in item else None,
            angle=item["angle"] if "angle" in item else None,
            gravity=item["gravity"] if "gravity" in item else False,
            sprites=item["sprites"] if "sprites" in item else None,
        )
        emitter_configs.append(config)

    return emitter_configs


def uv_for_16(ix: int) -> tuple[int, int]:
    col = ix % 8
    row = ix // 8
    return col * 8, row * 8


class Anim:
    emitters: list[EmitterConfig]

    def __init__(
        self, x: int, y: int, emitters: list[EmitterConfig], play_speed: float = 1.0
    ):
        self.emitters = emitters
        self.inner = []
        self.x = x
        self.y = y
        self.timer = 0
        self.dead = False
        self.play_speed = play_speed
        self.duration = max(ec.duration or 1 for ec in emitters)
        for ec in emitters:
            e = emitter.create(x, y, ec.frequency, ec.max_p)
            if isinstance(ec.size, Sequence):
                ps_set_size(e, *ec.size)
            else:
                ps_set_size(e, ec.size)
            ps_set_speed(ec, ec.speed)
            if isinstance(ec.life, Sequence):
                ps_set_life(e, *ec.life)
            else:
                ps_set_life(e, ec.life)
            if ec.colors:
                ps_set_colours(e, lua.table(*ec.colors))
            if ec.sprites:
                ps_set_sprites(e, lua.table(*ec.sprites))
            if ec.area:
                if isinstance(ec.area, Sequence):
                    ps_set_area(e, *ec.area)
                else:
                    ps_set_area(e, ec.area)
            if ec.burst:
                ps_set_burst(e, *ec.burst)
            if ec.angle:
                if isinstance(ec.angle, Sequence):
                    ps_set_angle(e, *ec.angle)
                else:
                    ps_set_angle(e, ec.angle)
            self.inner.append(e)

    def update(self):
        for e in self.inner:
            e.update(e, 1 / 30 * self.play_speed)
            e.draw(e)
        self.timer += 1
        total_num_particles = 0
        if self.timer and self.timer % (30 * 3) == 0:
            for e in self.inner:
                total_num_particles += len(e.particles)
            if total_num_particles == 0:
                self.dead = True
        if self.timer >= self.duration * 30:
            for e in self.inner:
                if e.is_emitting(e):
                    e.stop_emit(e)

    def draw(self):
        for _v in list(lua.globals().draw_calls.values()):
            v = dict(_v)
            match v:
                case {"t": "circfill", "x": x, "y": y, "r": r, "c": c}:
                    pyxel.circ(x, y, r, c)
                case {"t": "spr", "n": n, "x": x, "y": y}:
                    u, v = uv_for_16(n)
                    pyxel.blt(x, y, 1, u, v, 8, 8, 0)
                case _:
                    raise ValueError(f"Unknown draw call: {v}")
        lua.globals().draw_calls = lua.table()

    @staticmethod
    def from_predef(name: str, x: int, y: int, play_speed: float = 1.0) -> Anim:
        if isinstance(name, str):
            config = access_predef(name)
        else:
            config = name
        emitters = convert_to_emitter_configs(config)
        return Anim(x, y, emitters, play_speed)


lua = LuaRuntime(unpack_returned_tuples=True)
with open("assets/ps.lua54.lua") as f:
    lua.execute(f.read())

# emitters = []
ps_set_size = lua.globals().ps_set_size
ps_set_speed = lua.globals().ps_set_speed
ps_set_life = lua.globals().ps_set_life
ps_set_colours = lua.globals().ps_set_colours
ps_set_area = lua.globals().ps_set_area
ps_set_burst = lua.globals().ps_set_burst
ps_set_angle = lua.globals().ps_set_angle
ps_set_gravity = lua.globals().ps_set_gravity
ps_set_sprites = lua.globals().ps_set_sprites
emitter = lua.globals().emitter


def flush_draw_calls():
    for v in list(lua.globals().draw_calls.values()):
        print(dict(v))
    lua.globals().draw_calls = lua.table()


# explo = emitter.create(120, 120, 0, 30) # omit the first two -- they are coordinates, the last two are frequency and max particles
# ps_set_size(explo, 4, 0, 3, 0)
# ps_set_speed(explo, 0)
# ps_set_life(explo, 1)
# ps_set_colours(explo, lua.table(7, 6, 5))
# ps_set_area(explo, 30, 30)
# ps_set_burst(explo, True, 10)
# emitters.append(explo)

# spray = emitter.create(120, 120, 0, 80)
# ps_set_size(spray, 0)
# ps_set_speed(spray, 20, 10, 20, 10)
# ps_set_colours(spray, lua.table(7, 6, 5))
# ps_set_life(spray, 0, 1.3)
# ps_set_burst(spray, True, 30)
# emitters.append(spray)

# for _ in range(60):
#     explo.update(explo, 1/60)
#     explo.draw(explo)
#     flush_draw_calls()

# def update_emitters():
#     for e in emitters:
#         e.update(e, 1/30)
#         e.draw(e)

# def draw_emitters():
#     for _v in list(lua.globals().draw_calls.values()):
#         v = dict(_v)
#         print(v)
#         match v:
#             case {'t': 'circfill', 'x': x, 'y': y, 'r': r, 'c': c}:
#                 pyxel.circ(x, y, r, c)
#             case {'t': 'spr', 'n': n, 'x': x, 'y': y}:
#                 pyxel.blt(x, y, 1, n*16, 0, 8, 8, 0)
#             case _:
#                 raise ValueError(f"Unknown draw call: {v}")
#     lua.globals().draw_calls = lua.table()
