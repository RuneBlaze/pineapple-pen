from genio.effect import DamageEffect, parse_targeted_effect


def test_parse_targeted_effect():
    modifier = "[entity: shield 10 | crit 0.5 | delay 1]"
    expected_result = (
        "entity",
        DamageEffect(
            delta_shield=10,
            delta_hp=0,
            critical_chance=0.5,
            delay=1,
            pierce=False,
            drain=False,
            accuracy=1.0,
        ),
    )
    assert parse_targeted_effect(modifier) == expected_result

    modifier = "[entity: damaged 5 | acc 0.8 | delay 2 | pierce | drain]"
    expected_result = (
        "entity",
        DamageEffect(
            delta_shield=0,
            delta_hp=-5,
            critical_chance=0.0,
            delay=2,
            pierce=True,
            drain=True,
            accuracy=0.8,
        ),
    )
    assert parse_targeted_effect(modifier) == expected_result

    modifier = "[entity: healed 3 | crit 0.2 | delay 0]"
    expected_result = (
        "entity",
        DamageEffect(
            delta_shield=0,
            delta_hp=3,
            critical_chance=0.2,
            delay=0,
            pierce=False,
            drain=False,
            accuracy=1.0,
        ),
    )
    assert parse_targeted_effect(modifier) == expected_result
