"""Particle Systems"""
from __future__ import annotations

from collections import deque
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
    delta_x: int | None = None
    delta_y: int | None = None
    appear_delay: int = 0
    rnd_color: bool = False

    def __post_init__(self):
        self.appear_delay = self.appear_delay or 0


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
            delta_x=item["delta_x"] if "delta_x" in item else None,
            delta_y=item["delta_y"] if "delta_y" in item else None,
            appear_delay=item["appear_delay"] if "appear_delay" in item else None,
            rnd_color=item["rnd_color"] if "rnd_color" in item else False,
        )
        emitter_configs.append(config)

    return emitter_configs


def uv_for_16(ix: int) -> tuple[int, int]:
    col = ix % 8
    row = ix // 8
    return col * 8, row * 8


class Anim:
    emitters: list[EmitterConfig]
    queued: deque[EmitterConfig]

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
        self.queued = []
        for ec in emitters:
            self.queued.append(ec)
        self.queued = deque(sorted(self.queued, key=lambda x: x.appear_delay))
        self.flush_queued()

    def flush_queued(self):
        while self.queued and self.queued[0].appear_delay <= self.timer:
            ec = self.queued.popleft()
            self.create_from_config(ec)

    def create_from_config(self, ec: EmitterConfig):
        x, y = self.x, self.y
        x += ec.delta_x or 0
        y += ec.delta_y or 0
        e = emitter.create(x, y, ec.frequency, ec.max_p)
        if isinstance(ec.size, Sequence):
            ps_set_size(e, *ec.size)
        else:
            ps_set_size(e, ec.size)
        if isinstance(ec.speed, Sequence):
            ps_set_speed(e, *ec.speed)
        else:
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
        if ec.gravity:
            ps_set_gravity(e, True)
        if ec.rnd_color:
            ps_set_rnd_colour(e, True)
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
ps_set_rnd_colour = lua.globals().ps_set_rnd_colour
emitter = lua.globals().emitter


def flush_draw_calls():
    for v in list(lua.globals().draw_calls.values()):
        print(dict(v))
    lua.globals().draw_calls = lua.table()
