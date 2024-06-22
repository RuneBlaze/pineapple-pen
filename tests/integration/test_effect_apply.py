from genio.battle import setup_battle_bundle
from genio.effect import SinglePointEffect


def test_vulnerable_modifies_damage_correctly():
    bundle = setup_battle_bundle("initial_deck", "players.starter", ["enemies.slime"])
    bundle.process_and_flush_effects(
        "[Slime A: +vulnerable [1 turn] [ME: damaged {:d}] -> [ME: damaged {{m[0] * 1.25}}];]"
    )
    assert bundle.enemies[0].status_effects
    flushed = bundle.process_and_flush_effects("[Slime A: damaged 4]")
    match flushed[0][1]:
        case SinglePointEffect(_) as effect:
            assert effect.damage == 5
        case _:
            assert False, "Invalid effect"


def test_end_of_turn_damages_correctly():
    bundle = setup_battle_bundle("initial_deck", "players.starter", ["enemies.slime"])
    bundle.process_and_flush_effects(
        "[Slime A: +burn [1 turn] [ME: end of turn] -> [ME: damaged 1];]"
    )
    bundle.process_and_flush_effects(
        "[Slime A: +poison [1 turn] [ME: end of turn] -> [ME: damaged 3];]"
    )

    bundle.on_turn_end()

    slime = bundle.search("Slime A")
    assert slime.hp == slime.max_hp - 4
