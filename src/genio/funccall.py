import inspect
import re
import textwrap
from dataclasses import dataclass, fields, is_dataclass
from typing import Annotated, Type, Union, get_args, get_origin, Any

import google.ai.generativelanguage as glm
import google.generativeai as genai
from icecream import ic


def dataclass_to_glm_schema(dc: Type) -> glm.Schema:
    """
    Convert a dataclass to a Generative Language Model schema.
    """
    if not is_dataclass(dc):
        raise TypeError("Input must be a dataclass")

    properties = {}
    for field in fields(dc):
        field_schema = _field_type_to_glm_schema(field.type)
        properties[field.name] = field_schema

    return glm.Schema(
        type=glm.Type.OBJECT,
        properties=properties,
        required=[field.name for field in fields(dc) if not field.default],
    )


def _field_type_to_glm_schema(field_type: Type) -> glm.Schema:
    if get_origin(field_type) is Union:  # Handle Optional[T]
        args = get_args(field_type)
        if type(None) in args:
            field_type = args[0] if args[0] is not type(None) else args[1]
        else:
            raise TypeError("Unsupported Optional type: must be Optional[T] or None")

    if get_origin(field_type) is Annotated:  # Check for Annotated fields
        args = get_args(field_type)
        field_type = args[0]  # Extract the underlying type
        description = args[1]
    else:
        description = None

    # Basic type mapping
    type_map = {
        str: glm.Type.STRING,
        int: glm.Type.NUMBER,
        float: glm.Type.NUMBER,
        bool: glm.Type.BOOLEAN,
    }

    if field_type in type_map:
        return glm.Schema(type=type_map[field_type], description=description)
    elif is_dataclass(field_type):  # Recursion for nested dataclasses
        return dataclass_to_glm_schema(field_type)
    else:
        raise TypeError(f"Unsupported field type: {field_type}")


def dataclass_to_function_declaration(dc: Type) -> glm.FunctionDeclaration:
    """
    Converts a dataclass to a GLM FunctionDeclaration.
    """
    if not is_dataclass(dc):
        raise TypeError("Input must be a dataclass")

    name = _to_snake_case(dc.__name__)
    description = inspect.getdoc(dc)  # Get the dataclass docstring
    if description:
        description = textwrap.dedent(description)

    return glm.FunctionDeclaration(
        name=name, description=description, parameters=dataclass_to_glm_schema(dc)
    )


def _to_snake_case(name: str) -> str:
    """Converts a CamelCase name to snake_case."""
    name = re.sub(
        "(.)([A-Z][a-z]+)", r"\1_\2", name
    )  # Insert '_' before lowercase -> Uppercase
    return re.sub(
        "([a-z0-9])([A-Z])", r"\1_\2", name
    ).lower()  # Insert '_' before Uppercase


@dataclass
class Attack:
    target: str

@dataclass
class Cast:
    spell: str
    target: str


def prompt_for_structured_output(prompt: str, types: list[Type]) -> Any:
    function_decls = [dataclass_to_function_declaration(t) for t in types]
    snake2type = {_to_snake_case(t.__name__): t for t in types}
    tool = glm.Tool(function_declarations=function_decls)
    model = genai.GenerativeModel(model_name='gemini-1.0-pro', tools=tool)
    chat = model.start_chat()
    response = chat.send_message(prompt)
    fc = response.candidates[0].content.parts[0].function_call
    dictionary = type(fc).to_dict(fc)
    name = dictionary['name']
    try:
        return recursive_instantiate(snake2type[name], dictionary['args'])
    except ValueError as e:
        chat


def recursive_instantiate(dc: Type, dictionary: dict) -> Any:
    if not is_dataclass(dc):
        raise TypeError("Input must be a dataclass")

    if not isinstance(dictionary, dict):
        raise TypeError("Input must be a dictionary")

    kwargs = {}
    for field in fields(dc):
        field_name = field.name
        if field_name not in dictionary:
            raise ValueError(f"Missing field '{field_name}' in dictionary")

        field_value = dictionary[field_name]
        if is_dataclass(field.type):
            field_value = recursive_instantiate(field.type, field_value)

        kwargs[field_name] = field_value

    return dc(**kwargs)

if __name__ == "__main__":
    r = prompt_for_structured_output("I'm designing a turn-based combat system for a game. A goblin attacks a knight. What actions could the knight take in response? Be creative; don't just attack.", [Attack, Cast])
    ic(r)