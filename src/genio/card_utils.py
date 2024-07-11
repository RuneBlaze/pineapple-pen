from typing import Protocol

from genio.ps import Anim, HasPos


class CanAddAnim(Protocol):
    def add_anim(
        self,
        name: str,
        x: int,
        y: int,
        play_speed: float = 1.0,
        attached_to: HasPos | None = None,
    ) -> Anim:
        ...
