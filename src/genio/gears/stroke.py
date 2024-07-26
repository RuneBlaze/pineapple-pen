from genio.components import CanAddAnim
from genio.tween import Tweener


class StrokeAnim:
    def __init__(self, x: int, y: int, width: int, parent: CanAddAnim) -> None:
        self.tweener = Tweener()
        self.x = x
        self.y = y
        self.tweener.append_mutate(
            self,
            lens="x",
            duration=40,
            target_value=self.x + width,
            tween_type="ease_in_out_quad",
        )
        self.parent = parent
        self.parent.add_anim(
            "anims.stroke",
            self.x,
            self.y,
            1,
            attached_to=self,
        )
        self.timer = 0

    def screen_pos(self) -> tuple[float, float]:
        return self.x, self.y

    def update(self) -> None:
        self.tweener.update()
        self.timer += 1

    def is_dead(self) -> bool:
        return self.timer > 60
