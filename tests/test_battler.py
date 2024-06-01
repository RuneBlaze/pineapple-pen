from genio.battle.battler import (
    BattleManager,
    Battler,
    DMTools,
    ItemLike,
    extract_double_quoted_words,
)
from pytest import fixture


@fixture
def battle_manager():
    # Define some skills for testing using the ItemLike class
    fireball = ItemLike(
        name="Fireball",
        cost=10,
        effects=[
            "A powerful fire spell that engulfs the target in flames.",
            "Damage formula: 2 * Attacker.matk - Defender.mdef",
            "Accuracy: 90%",
            "This skill has a 20% chance to inflict 'Burn' status on the target.",
        ],
        marks=[],
    )

    heal = ItemLike(
        name="Heal",
        cost=8,
        effects=[
            "A healing spell that restores health to a single ally.",
            "Healing formula: 3 * Attacker.matk",
            "Accuracy: 100%",
            "This skill removes 'Poison' and 'Burn' status effects from the target.",
        ],
        marks=[],
    )

    slash = ItemLike(
        name="Slash",
        cost=5,
        effects=[
            "A quick physical attack with a sharp blade.",
            "Damage formula: Attacker.patk - Defender.pdef",
            "Accuracy: 95%",
            "This skill has a 10% chance to cause 'Bleed' status on the target.",
        ],
        marks=[],
    )

    shield = ItemLike(
        name="Shield",
        cost=12,
        effects=[
            "A protective spell that increases defense.",
            "Effect formula: Increase pdef by 50",
            "Duration: 3 turns",
            "This skill has a 100% chance to succeed.",
        ],
        marks=[],
    )

    # Define a normal "Attack" ItemLike for Slime and Goblin
    normal_attack = ItemLike(
        name="Attack",
        cost=0,
        effects=[
            "A basic physical attack.",
            "Damage formula: Attacker.patk - Defender.pdef",
            "Accuracy: 100%",
        ],
        marks=[],
    )

    # Define some allies and enemies for testing
    allies = [
        Battler(
            "Ralph",
            {
                "hp": 1500,
                "mp": 200,
                "patk": 250,
                "pdef": 150,
                "matk": 100,
                "mdef": 100,
                "agi": 80,
                "eva": 10,
            },
            items=[slash, shield],
        ),
        Battler(
            "Lucy",
            {
                "hp": 1200,
                "mp": 300,
                "patk": 200,
                "pdef": 120,
                "matk": 150,
                "mdef": 130,
                "agi": 90,
                "eva": 20,
            },
            items=[fireball, heal],
        ),
    ]

    enemies = [
        Battler(
            "Slime 1",
            {
                "hp": 500,
                "mp": 50,
                "patk": 50,
                "pdef": 20,
                "matk": 30,
                "mdef": 20,
                "agi": 30,
                "eva": 5,
            },
            items=[normal_attack],
        ),
        Battler(
            "Goblin",
            {
                "hp": 800,
                "mp": 80,
                "patk": 80,
                "pdef": 40,
                "matk": 40,
                "mdef": 40,
                "agi": 40,
                "eva": 10,
            },
            items=[normal_attack],
        ),
    ]
    return BattleManager(allies, enemies)


def test_dm_tools_trivial(battle_manager: BattleManager):
    tools = DMTools(battle_manager)
    assert tools.prob_check(0.5) in [True, False]
    assert tools.prob_check(1)
    assert (ralph := tools.battler("ralph")).name == "Ralph"

    assert ralph.eva == ralph.stats["eva"]
    assert ralph.agi == ralph.stats["agi"]
    assert ralph.patk == ralph.stats["patk"]

    assert ralph.hp == ralph.mhp
    assert ralph.agi is not None

    original_mhp = ralph.mhp
    ralph.receive_damage(100_000_000)
    assert ralph.hp == 0
    assert ralph.mhp == original_mhp


def test_extract_double_quoted_words():
    s = 'This is a "test" string with "double" quoted words.'
    expected = ["test", "double"]
    assert extract_double_quoted_words(s) == expected
