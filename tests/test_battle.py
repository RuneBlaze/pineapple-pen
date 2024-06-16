import numpy as np
import pytest
from genio.battle import (
    BattleBundle,
    BattlePrelude,
    Battler,
    CardBundle,
    EnemyBattler,
    EnemyProfile,
    PlayerBattler,
    PlayerProfile,
)
from genio.effect import DamageEffect


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


def test_apply_damage_with_shield():
    player_profile = PlayerProfile(name="Player", hit_points=30, profile="Warrior")
    player = Battler(profile=player_profile, hp=30, max_hp=30, shield_points=3)
    enemy_profile = EnemyProfile(
        name="Enemy", hit_points=20, description="A fierce enemy", pattern=["attack"]
    )
    enemy = Battler(profile=enemy_profile, hp=20, max_hp=20, shield_points=0)
    battle_prelude = BattlePrelude(description="An epic battle")
    card_bundle = CardBundle.from_predef("initial_deck")

    battle_bundle = BattleBundle(
        player=player,
        enemies=[enemy],
        battle_prelude=battle_prelude,
        card_bundle=card_bundle,
    )

    damage_effect = DamageEffect(
        delta_hp=-9,
        delta_shield=0,
        accuracy=1.0,
        pierce=False,
        critical_chance=0.0,
        drain=False,
    )
    rng = np.random.default_rng(42)
    battle_bundle.apply_effect(None, player, damage_effect, rng)

    assert player.hp == 24
    assert player.shield_points == 0


def test_apply_piercing_damage():
    player_profile = PlayerProfile(name="Player", hit_points=30, profile="Warrior")
    player = Battler(profile=player_profile, hp=30, max_hp=30, shield_points=3)
    enemy_profile = EnemyProfile(
        name="Enemy", hit_points=20, description="A fierce enemy", pattern=["attack"]
    )
    enemy = Battler(profile=enemy_profile, hp=20, max_hp=20, shield_points=0)
    battle_prelude = BattlePrelude(description="An epic battle")
    card_bundle = CardBundle.from_predef("initial_deck")

    battle_bundle = BattleBundle(
        player=player,
        enemies=[enemy],
        battle_prelude=battle_prelude,
        card_bundle=card_bundle,
    )

    damage_effect = DamageEffect(
        delta_hp=-9,
        delta_shield=0,
        accuracy=1.0,
        pierce=True,
        critical_chance=0.0,
        drain=False,
    )
    rng = np.random.default_rng(42)
    battle_bundle.apply_effect(None, player, damage_effect, rng)

    assert player.hp == 21
    assert player.shield_points == 3


def test_apply_healing():
    player_profile = PlayerProfile(name="Player", hit_points=30, profile="Warrior")
    player = Battler(profile=player_profile, hp=20, max_hp=30, shield_points=0)
    enemy_profile = EnemyProfile(
        name="Enemy", hit_points=20, description="A fierce enemy", pattern=["attack"]
    )
    enemy = Battler(profile=enemy_profile, hp=20, max_hp=20, shield_points=0)
    battle_prelude = BattlePrelude(description="An epic battle")
    card_bundle = CardBundle.from_predef("initial_deck")

    battle_bundle = BattleBundle(
        player=player,
        enemies=[enemy],
        battle_prelude=battle_prelude,
        card_bundle=card_bundle,
    )

    healing_effect = DamageEffect(
        delta_hp=15,
        delta_shield=0,
        accuracy=1.0,
        pierce=False,
        critical_chance=0.0,
        drain=False,
    )
    rng = np.random.default_rng(42)
    battle_bundle.apply_effect(None, player, healing_effect, rng)

    assert player.hp == 30
