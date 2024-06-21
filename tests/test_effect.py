from genio.effect import SinglePointEffect, TargetedEffect, parse_targeted_effect


def targeted_effect_equals_except_uuid(
    lhs: TargetedEffect, rhs: TargetedEffect
) -> bool:
    return lhs[1].equals_except_uuid(rhs[1]) and lhs[0] == rhs[0]


def test_parse_targeted_effect():
    modifier = "[entity: shield 10 | crit 0.5 | delay 1]"
    expected_result = (
        "entity",
        SinglePointEffect(
            delta_shield=10,
            delta_hp=0,
            critical_chance=0.5,
            delay=1,
            pierce=False,
            drain=False,
            accuracy=1.0,
        ),
    )
    assert targeted_effect_equals_except_uuid(
        parse_targeted_effect(modifier), expected_result
    )

    modifier = "[entity: damaged 5 | acc 0.8 | delay 2 | pierce | drain]"
    expected_result = (
        "entity",
        SinglePointEffect(
            delta_shield=0,
            delta_hp=-5,
            critical_chance=0.0,
            delay=2,
            pierce=True,
            drain=True,
            accuracy=0.8,
        ),
    )
    assert targeted_effect_equals_except_uuid(
        parse_targeted_effect(modifier), expected_result
    )

    modifier = "[entity: healed 3 | crit 0.2 | delay 0]"
    expected_result = (
        "entity",
        SinglePointEffect(
            delta_shield=0,
            delta_hp=3,
            critical_chance=0.2,
            delay=0,
            pierce=False,
            drain=False,
            accuracy=1.0,
        ),
    )
    assert targeted_effect_equals_except_uuid(
        parse_targeted_effect(modifier), expected_result
    )


def test_parse_targeted_effect_status_effect():
    _, effect = parse_targeted_effect(
        "[entity: +vulnerable [3 turns] [foo: {:d}] -> [foo: {{m[0] * 1.5}}];]"
    )
    defn, counter = effect.add_status
    assert defn.counter_type == "turns"
    assert counter == 3
    assert defn.name == "vulnerable"
    assert defn.subst.pattern == "[foo: {:d}]"
