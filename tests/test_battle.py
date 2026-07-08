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
    calculate_energy_cost,
)
from genio.card import Card
from genio.effect import SinglePointEffect


@pytest.fixture
def card_bundle():
    return CardBundle.from_predef("initial_deck")


def test_battlers_basic(card_bundle):
    player = PlayerBattler.from_predef("players.starter")
    enemy1 = EnemyBattler.from_predef("enemies.slime")
    enemy2 = EnemyBattler.from_predef("enemies.slime")
    manager = BattleBundle(
        player, [enemy1, enemy2], BattlePrelude.default(), card_bundle
    )

    battlers = list(manager.battlers())

    assert len(battlers) == 3
    assert player in battlers
    assert enemy1 in battlers


def test_sts_turn_baseline(card_bundle):
    player = PlayerBattler.from_predef("players.starter")
    enemy = EnemyBattler.from_predef("enemies.slime")
    manager = BattleBundle(player, [enemy], BattlePrelude.default(), card_bundle)

    assert player.name_stem == "Typist"
    assert player.max_hp == 80
    assert card_bundle.default_draw_count == 5
    assert manager.default_energy == 3


def test_discrete_card_energy_costs():
    assert calculate_energy_cost([Card("Strike")]) == 1
    assert calculate_energy_cost([Card("Bash")]) == 2
    assert calculate_energy_cost([Card("Dash", energy_cost=1)]) == 1
    assert calculate_energy_cost([Card("Letter Replacer")]) == 0
    assert calculate_energy_cost([Card("Strike"), Card("Bash")]) == 3


def test_initial_deck_contains_typist_special_cards(card_bundle):
    assert [card.name for card in card_bundle.deck].count("Strike") == 4
    assert [card.name for card in card_bundle.deck].count("Defend") == 4

    prefix_cards = [card for card in card_bundle.deck if card.is_prefix_card()]
    replacer_cards = [
        card for card in card_bundle.deck if card.name.lower() == "letter replacer"
    ]

    assert len(prefix_cards) == 1
    prefix_card = prefix_cards[0]
    assert prefix_card.prefix == "D"
    assert prefix_card.prefix_min_length == 4
    assert prefix_card.prefix_max_length == 8
    assert prefix_card.energy_cost == 1
    assert len(replacer_cards) == 1
    assert replacer_cards[0].energy_cost == 0


def test_temporary_card_transform_reverts():
    card = Card("Strike", "Deal 6 damage.")

    card.begin_temporary_transform("Stroke", "Draw 1 card.")

    assert card.name == "Stroke"
    assert card.description == "Draw 1 card."
    assert card.has_temporary_transform()

    card.revert_temporary_transform()

    assert card.name == "Strike"
    assert card.description == "Deal 6 damage."
    assert not card.has_temporary_transform()


def test_card_bundle_reverts_temporary_transforms():
    card = Card("Strike", "Deal 6 damage.")
    card_bundle = CardBundle([card])
    drawn = next(card_bundle.draw(1))
    drawn.begin_temporary_transform("Stroke", "Draw 1 card.")
    card_bundle.graveyard.append(drawn)

    card_bundle.revert_temporary_transforms()

    assert drawn.name == "Strike"
    assert drawn.description == "Deal 6 damage."


def test_prefix_card_randomizes_on_each_draw():
    prefix_card = Card(
        name="D",
        prefix="D",
        prefix_min_length=4,
        prefix_max_length=8,
        energy_cost=2,
    )
    card_bundle = CardBundle([prefix_card])

    drawn = next(card_bundle.draw(1))
    assert drawn.name.startswith("D")
    assert set(drawn.name[1:]) == {"_"}
    assert 4 <= len(drawn.name) <= 8
    assert not drawn.is_playable_prefix_state()

    drawn.set_prefix_suffix("a" * drawn.prefix_suffix_length())
    drawn.confirm_prefix_entry()
    drawn.finish_prefix_description("Deal a strange burst of damage.")
    assert drawn.is_playable_prefix_state()

    card_bundle.graveyard.append(drawn)
    drawn_again = next(card_bundle.draw(1))
    assert drawn_again is drawn
    assert drawn_again.description is None
    assert drawn_again.prefix_typed == ""
    assert drawn_again.name.startswith("D")
    assert set(drawn_again.name[1:]) == {"_"}
    assert 4 <= len(drawn_again.name) <= 8


def test_known_sts_cards_resolve_without_llm(card_bundle):
    player = PlayerBattler.from_predef("players.starter")
    enemy = EnemyBattler.from_predef("enemies.sneaky_gremlin")
    manager = BattleBundle(player, [enemy], BattlePrelude.default(), card_bundle)

    manager.resolve_player_cards([Card("Strike")])
    assert enemy.hp == 24

    manager.resolve_player_cards([Card("Defend")])
    assert player.shield_points == 5

    manager.replenish_energy()
    manager.resolve_player_cards([Card("Bash")])
    assert enemy.hp == 16
    assert enemy.status_effects[0].name == "vulnerable"


def test_simple_generated_fallback_card_resolves_without_llm(card_bundle):
    player = PlayerBattler.from_predef("players.starter")
    enemy = EnemyBattler.from_predef("enemies.sneaky_gremlin")
    manager = BattleBundle(player, [enemy], BattlePrelude.default(), card_bundle)

    manager.resolve_player_cards([Card("Dash", "Deal 6 damage.")])

    assert enemy.hp == 24


def test_player_card_inference_gate(card_bundle):
    player = PlayerBattler.from_predef("players.starter")
    enemy = EnemyBattler.from_predef("enemies.sneaky_gremlin")
    manager = BattleBundle(player, [enemy], BattlePrelude.default(), card_bundle)

    assert not manager.player_cards_need_inference([Card("Strike")])
    assert not manager.player_cards_need_inference([Card("Dash", "Deal 6 damage.")])
    assert manager.player_cards_need_inference([Card("Dash", "Gain 2 speed.")])
    assert manager.player_cards_need_inference([Card("Strike"), Card("Defend")])


def test_simple_enemy_intent_resolves_without_llm(card_bundle):
    player = PlayerBattler.from_predef("players.starter")
    enemy = EnemyBattler.from_predef("enemies.sneaky_gremlin")
    manager = BattleBundle(player, [enemy], BattlePrelude.default(), card_bundle)

    manager.resolve_enemy_actions()

    assert player.hp == 70


def test_enemy_action_inference_gate(card_bundle):
    player = PlayerBattler.from_predef("players.starter")
    enemy = EnemyBattler.from_predef("enemies.sneaky_gremlin")
    manager = BattleBundle(player, [enemy], BattlePrelude.default(), card_bundle)

    assert not manager.enemy_actions_need_inference()

    enemy.current_intent = "make a weird threat"

    assert manager.enemy_actions_need_inference()


def test_search_existing_battler():
    player = PlayerBattler.from_predef("players.starter")
    enemy1 = EnemyBattler.from_predef("enemies.slime")
    enemy2 = EnemyBattler.from_predef("enemies.slime")
    manager = BattleBundle(
        player, [enemy1, enemy2], BattlePrelude.default(), card_bundle
    )
    battler = manager.search(player.name)
    assert battler == player


def test_search_non_existing_battler(card_bundle):
    player = PlayerBattler.from_predef("players.starter")
    enemy1 = EnemyBattler.from_predef("enemies.slime")
    enemy2 = EnemyBattler.from_predef("enemies.slime")
    manager = BattleBundle(
        player, [enemy1, enemy2], BattlePrelude.default(), card_bundle
    )
    with pytest.raises(ValueError):
        manager.search("NonExistingBattler")


def test_apply_damage_with_shield():
    player_profile = PlayerProfile(name="Player", hit_points=30, profile="Warrior")
    player = Battler(profile=player_profile, hp=30, max_hp=30, shield_points=3)
    enemy_profile = EnemyProfile(
        name="Enemy", hit_points=20, description="A fierce enemy", pattern=["attack"]
    )
    enemy = Battler(profile=enemy_profile, hp=20, max_hp=20, shield_points=0)
    battle_prelude = BattlePrelude(description="An epic battle")

    battle_bundle = BattleBundle(
        player=player,
        enemies=[enemy],
        battle_prelude=battle_prelude,
        card_bundle=card_bundle,
    )

    damage_effect = SinglePointEffect.from_damage(9)
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

    damage_effect = SinglePointEffect.from_damage(9, pierce=True)
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

    healing_effect = SinglePointEffect.from_heal(10)
    rng = np.random.default_rng(42)
    battle_bundle.apply_effect(None, player, healing_effect, rng)

    assert player.hp == 30
