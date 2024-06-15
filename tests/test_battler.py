import numpy as np
import pytest
from genio.battle import BattleBundle, BattlePrelude, EnemyBattler, PlayerBattler


def test_battlers_basic():
    player = PlayerBattler.from_predef("players.starter")
    enemy1 = EnemyBattler.from_predef("enemies.slime")
    enemy2 = EnemyBattler.from_predef("enemies.slime")
    manager = BattleBundle(player, [enemy1, enemy2], BattlePrelude.default())

    battlers = list(manager.battlers())

    assert len(battlers) == 3
    assert player in battlers
    assert enemy1 in battlers


def test_search_existing_battler():
    player = PlayerBattler.from_predef("players.starter")
    enemy1 = EnemyBattler.from_predef("enemies.slime")
    enemy2 = EnemyBattler.from_predef("enemies.slime")
    manager = BattleBundle(player, [enemy1, enemy2], BattlePrelude.default())
    battler = manager.search(player.name)
    assert battler == player


def test_search_non_existing_battler():
    player = PlayerBattler.from_predef("players.starter")
    enemy1 = EnemyBattler.from_predef("enemies.slime")
    enemy2 = EnemyBattler.from_predef("enemies.slime")
    manager = BattleBundle(player, [enemy1, enemy2], BattlePrelude.default())
    with pytest.raises(ValueError):
        manager.search("NonExistingBattler")


def test_resolve_result():
    player = PlayerBattler.from_predef("players.starter")
    enemy1 = EnemyBattler.from_predef("enemies.slime")
    enemy2 = EnemyBattler.from_predef("enemies.slime")
    manager = BattleBundle(player, [enemy1, enemy2], BattlePrelude.default())
    result = "[celine: damaged 10]"
    manager.resolve_result(result)
    manager.flush_effects(np.random.default_rng())
    assert player.hp == player.max_hp - 10
