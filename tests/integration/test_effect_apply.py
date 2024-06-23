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


def test_counter_based_correctly():
    bundle = setup_battle_bundle("initial_deck", "players.starter", ["enemies.slime"])
    assert bundle.process_and_flush_effects("[Slime A: damaged 3]").total_damage() == 3
    bundle.process_and_flush_effects(
        "[Slime A: +diamond block [2 times] [ME: damaged {:d}] if m[0] <= 2 -> [ME: damaged 0];]"
    )
    assert bundle.process_and_flush_effects("[Slime A: damaged 3]").total_damage() == 3
    assert bundle.process_and_flush_effects("[Slime A: damaged 1]").total_damage() == 0
    assert bundle.process_and_flush_effects("[Slime A: damaged 1]").total_damage() == 0
    assert bundle.process_and_flush_effects("[Slime A: damaged 1]").total_damage() == 1


def test_damage_by_correctly():
    bundle = setup_battle_bundle("initial_deck", "players.starter", ["enemies.slime"])
    bundle.process_and_flush_effects(
        "[Celine: +strength [3 times] [{}: damaged {:d} by ME] -> [{{m[0]}}: damaged {{m[1] * 1.25}} by ME];]"
    )
    assert bundle.process_and_flush_effects("[Slime A: damaged 4 by celine]").total_damage() == 5
