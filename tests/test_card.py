from genio.core.card import ModelBuilder


def test_model_builder_trivial():
    builder = ModelBuilder()
    model = (
        builder.set_name("DynamicFoobarModel")
        .set_doc("This is a dynamically generated Foobar model.")
        .add_string_field("foo", "Input annotation for foo")
        .add_int_field("bar", "Input annotation for bar", 123)
        .build()
    )
    instance = model(foo="test")
    assert instance.foo == "test"
    assert instance.bar == 123
