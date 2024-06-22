from genio.effect import SinglePointEffect
from genio.utils import setup_battle_bundle


def test_vulnerable_modifies_damage_correctly():
    bundle = setup_battle_bundle(
        "initial_deck", "players.starter", ["enemies.slime"]
    )

    bundle.resolve_result('[Slime A: +vulnerable [1 turn] [ME: damaged {:d}] -> [ME: damaged {{m[0] * 1.25}}]')
    bundle.flush_effects()
    bundle.resolve_result('[Slime A: damaged 4]')
    flushed = bundle.flush_effects()
    match flushed[0][1]:
        case SinglePointEffect(_) as effect:
            assert effect.damage == 5
        case _:
            assert False, "Invalid effect"
