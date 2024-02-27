from jinja2 import Environment

jinja_env = Environment(
    block_start_string="{%",
    block_end_string="%}",
    variable_start_string="{",
    variable_end_string="}",
)

template = jinja_env.from_string("echo back to me: {foo['bar'].upper()}")

response = template.render({"foo": {"bar": "baz"}})
print(response)
