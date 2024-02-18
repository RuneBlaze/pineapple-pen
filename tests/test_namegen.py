from genio.namegen import NameGenerator


def test_name_generator_can_generate_name():
    generator = NameGenerator.default()

    name = generator.generate_name("m", "JP")
    assert name.first_name
    assert name.last_name
