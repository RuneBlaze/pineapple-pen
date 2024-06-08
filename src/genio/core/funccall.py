import inspect
import json
import re
import textwrap
from datetime import time
from typing import Annotated, Any, Literal, Union, get_args, get_origin

import google.ai.generativelanguage as glm
import google.generativeai as genai
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo
from structlog import get_logger

logger = get_logger()


def dataclass_to_glm_schema(dc: type[BaseModel]) -> glm.Schema:
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
        time: glm.Type.STRING,
    }

    if field_type in type_map:
        return glm.Schema(type=type_map[field_type], description=description)
    return dataclass_to_glm_schema(field_type)


def dataclass_to_function_declaration(dc: type) -> glm.FunctionDeclaration:
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


def extract_any_function_call(response) -> Any:
    for part in response.candidates[0].content.parts:
        if part.function_call:
            return part.function_call
    return None


def prompt_for_structured_output(prompt: str, types: list[type]) -> Any:
    function_decls = [dataclass_to_function_declaration(t) for t in types]
    snake2type = {_to_snake_case(t.__name__): t for t in types}
    tool = glm.Tool(function_declarations=function_decls)
    model = genai.GenerativeModel(model_name="gemini-1.0-pro", tools=tool)
    chat = model.start_chat()
    response = chat.send_message(prompt)
    logger.info(
        "prompting for structured output",
        prompt=prompt,
        types=types,
        cand0=response.candidates[0],
    )
    while True:
        fc = extract_any_function_call(response)
        if not fc:
            response = chat.send_message(
                f"I noticed an error in the previous response as it lacks a proper structured function call. Could you please reformat and address this issue by responding to the original request '{prompt}' with a structured function call? This format is necessary for processing your request effectively."
            )
            logger.warning("retrying", cand0=response.candidates[0])
            continue
        try:
            dictionary = type(fc).to_dict(fc)
            name = dictionary["name"]
            typ = snake2type[name]
            args = dictionary["args"]
            res = typ.model_validate(args)
            logger.info("validated", res=res)
            return res
        except ValidationError as e:
            response = chat.send_message(
                glm.Content(
                    parts=[
                        glm.Part(
                            function_response=glm.FunctionResponse(
                                name=name,
                                response={
                                    "status": "error",
                                    "reason": "Invalid Input: Your input couldn't be processed due to validating issues. Please revise and resubmit to fit the constraints.",
                                    "details": json.loads(e.json()),
                                },
                            )
                        )
                    ]
                )
            )
            logger.warning("retrying", error=e, cand0=response.candidates[0])
