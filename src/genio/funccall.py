import inspect
import re
import textwrap
from typing import Annotated, Type, Union, get_args, get_origin, Any, Literal

import google.ai.generativelanguage as glm
import google.generativeai as genai
from icecream import ic
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.fields import FieldInfo
from pydantic.alias_generators import to_snake
import json


def dataclass_to_glm_schema(dc: Type[BaseModel]) -> glm.Schema:
    """
    Convert a pydantic model to a Generative Language Model schema.
    """

    properties = {}
    for field_name, field_info in dc.model_fields.items():
        field_schema = _field_type_to_glm_schema(field_info)
        properties[field_name] = field_schema

    return glm.Schema(
        type=glm.Type.OBJECT,
        properties=properties,
        required=[
            field_name
            for field_name, field_info in dc.model_fields.items()
            if not field_info.default
        ],
    )


def _field_type_to_glm_schema(field_type: FieldInfo) -> glm.Schema:
    field_type = field_type.annotation
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

    if get_origin(field_type) is Literal:
        args = get_args(field_type)
        field_type = type(args[0])

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


class Attack(BaseModel):
    model_config = ConfigDict(alias_generator=to_snake)
    target: str


class Cast(BaseModel):
    model_config = ConfigDict(alias_generator=to_snake)
    spell: Literal["Hastega", "Quickga", "Slowga"]
    target: str


def transform_pydantic_error(error: ValidationError):
    simplified_errors = []
    for e in error.errors():
        simplified_errors.append(
            {
                "error_code": "invalid_input",  # You can customize the error code if needed
                "message": e["msg"],
                "fields": e["loc"],
            }
        )
    return simplified_errors


def prompt_for_structured_output(prompt: str, types: list[Type]) -> Any:
    function_decls = [dataclass_to_function_declaration(t) for t in types]
    snake2type = {_to_snake_case(t.__name__): t for t in types}
    tool = glm.Tool(function_declarations=function_decls)
    model = genai.GenerativeModel(model_name="gemini-1.0-pro", tools=tool)
    chat = model.start_chat()
    response = chat.send_message(prompt)
    while True:
        fc = response.candidates[0].content.parts[0].function_call
        dictionary = type(fc).to_dict(fc)
        name = dictionary["name"]
        if not response.candidates[0].content.parts[0].function_call:
            ic(response.candidates[0].content)
            response = chat.send_message(
                f"Thanks! Given this information. Can you help me with the original request correctly?\n> {prompt}\nPlease use function calling."
            )
            continue
        try:
            typ = snake2type[name]
            args = dictionary["args"]
            return typ.model_validate(args)
        except ValidationError as e:
            ic(json.loads(e.json()))
            response = chat.send_message(
                glm.Content(
                    parts=[
                        glm.Part(
                            function_response=glm.FunctionResponse(
                                name=name,
                                response={
                                    "status": "error",
                                    "reason": "invalid_input; please try again with better formatted input.",
                                    "details": json.loads(e.json()),
                                },
                            )
                        )
                    ]
                )
            )


# def recursive_instantiate(dc: Type, dictionary: dict) -> Any:
#     if not isinstance(dictionary, dict):
#         raise TypeError("Input must be a dictionary")

#     return dc.parse_obj(dictionary)

#     # kwargs = {}
#     # for field in fields(dc):
#     #     field_name = field.name
#     #     if field_name not in dictionary:
#     #         raise ValueError(f"Missing field '{field_name}' in dictionary")

#     #     field_value = dictionary[field_name]
#     #     if is_dataclass(field.type):
#     #         field_value = recursive_instantiate(field.type, field_value)

#     #     kwargs[field_name] = field_value

#     # return dc(**kwargs)

if __name__ == "__main__":
    # ic(dataclass_to_glm_schema(Attack))
    r = prompt_for_structured_output(
        "I'm designing a turn-based combat system for a game. A goblin attacks a knight. What actions could the knight take in response? Be creative; use cast.",
        [Attack, Cast],
    )
    ic(r)
