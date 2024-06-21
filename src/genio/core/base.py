from __future__ import annotations

import inspect
import json
import random
import re
from abc import ABC
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import time
from functools import cache, partial, wraps
from pathlib import Path
from textwrap import dedent
from typing import (
    Annotated,
    Any,
    TypeVar,
    get_args,
    get_origin,
    get_type_hints,
)

import tomlkit
import tomlkit as tomllib
import yaml
from icecream import ic
from jinja2 import BaseLoader, Environment, StrictUndefined, TemplateNotFound
from langchain.output_parsers import OutputFixingParser
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import ChatPromptTemplate
from scipy.stats import norm
from structlog import get_logger

from genio.utils.robustyaml import cleaning_parse

from .llm import aux_llm

logger = get_logger()

TEMPLATE_REGISTRY = {}
OUTPUT_FORMAT = "JSON"


def paragraph_consolidate(text: str) -> str:
    text = dedent(text).strip()
    buf = []
    flushed_paragraphs = []

    for line in text.splitlines():
        if re.match(r"^[^\w\d]", line.strip()):
            # If the line starts with a non-alphanumeric character,
            # flush current buffer and then flush this line
            if buf:
                flushed_paragraphs.append(" ".join(buf).strip())
                buf = []
            flushed_paragraphs.append(line)
        else:
            if not line.strip() and buf:
                # Flush the buffer if the line is empty and buffer is not
                flushed_paragraphs.append(" ".join(buf).strip())
                buf = []
            elif line.strip():
                # Add non-empty lines to the buffer
                buf.append(line.strip())

    # Flush remaining buffer
    if buf:
        flushed_paragraphs.append(" ".join(buf))

    return "\n\n".join(flushed_paragraphs).strip()


def access(structure, lens: str) -> Any:
    for key in lens.split("."):
        structure = structure[key]
    return structure


def can_access(structure, lens: str) -> bool:
    try:
        access(structure, lens)
        return True
    except KeyError:
        return False


PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class TemplateRegistryLoader(BaseLoader):
    def get_source(self, environment, template):
        if template in TEMPLATE_REGISTRY:
            return TEMPLATE_REGISTRY[template], template, lambda: True
        if (
            target_path := (PROJECT_ROOT / Path("assets/includes") / template)
        ).exists():
            return target_path.read_text(), str(target_path), lambda: True
        predef = slurp_toml("assets/strings.toml")
        if can_access(predef, template):
            return access(predef, template), template, lambda: True
        raise TemplateNotFound(template)


def naturalize(t: time) -> str:
    return t.strftime("%I:%M %p")


def humanize_zscore(zscore: float) -> str:
    if abs(zscore) < 0.01:
        return "perfectly average"
    directionality = "above" if zscore > 0 else "below"
    return f"{zscore:.2f} standard deviations {directionality} average"


def humanize_height_zscore(zscore: float) -> str:
    if abs(zscore) < 0.01:
        return "perfectly average in height for their age"

    directionality = "above" if zscore > 0 else "below"
    abs_zscore = abs(zscore)
    percentile = norm.cdf(zscore) * 100
    rounded_percentile = round(percentile, 1)

    if abs_zscore < 0.5:
        descriptor = "slightly"
        additional_info = "a bit taller" if zscore > 0 else "a bit shorter"
    elif abs_zscore < 1:
        descriptor = "a little"
        additional_info = "taller" if zscore > 0 else "shorter"
    elif abs_zscore < 2:
        descriptor = "moderately"
        additional_info = "quite tall" if zscore > 0 else "quite short"
    elif abs_zscore < 3:
        descriptor = "significantly"
        additional_info = "very tall" if zscore > 0 else "very short"
    else:
        descriptor = "extremely"
        additional_info = "huge for their age" if zscore > 0 else "tiny for their age"

    return f"{descriptor} {directionality} average in height for their age (around the {rounded_percentile}th percentile), {additional_info}"


jinja_env = Environment(
    loader=TemplateRegistryLoader(),
)
jinja_env.globals.update(zip=zip)
jinja_env.globals.update(naturalize=naturalize)
jinja_env.globals.update(humanize_zscore=humanize_zscore)
jinja_env.globals.update(humanize_height_zscore=humanize_height_zscore)
jinja_env.undefined = StrictUndefined


def jinja_global(func):
    jinja_env.globals[func.__name__] = func
    return func


def render_text(
    template: str, context: dict[str, Any], consolidate: bool = True
) -> str:
    template = jinja_env.from_string(template).render(context)
    if consolidate:
        return paragraph_consolidate(template)
    return template


def render_template(template: str, context: dict[str, Any]) -> ChatPromptTemplate:
    rendered_text = render_text(template, context)
    rendered_text = rendered_text.replace("{{", "TOK1")
    rendered_text = rendered_text.replace("}}", "TOK2")
    rendered_text = rendered_text.replace("{", "")
    rendered_text = rendered_text.replace("}", "")
    rendered_text = rendered_text.replace("TOK1", "{{")
    rendered_text = rendered_text.replace("TOK2", "}}")
    logger.info(rendered_text)
    return ChatPromptTemplate.from_template(rendered_text)


def tomlkit_to_popo(d):
    try:
        result = getattr(d, "value")
    except AttributeError:
        result = d

    if isinstance(result, list):
        result = [tomlkit_to_popo(x) for x in result]
    elif isinstance(result, dict):
        result = {
            tomlkit_to_popo(key): tomlkit_to_popo(val) for key, val in result.items()
        }
    elif isinstance(result, tomlkit.items.Integer):
        result = int(result)
    elif isinstance(result, tomlkit.items.Float):
        result = float(result)
    elif isinstance(result, tomlkit.items.String):
        result = str(result)
    elif isinstance(result, tomlkit.items.Bool):
        result = bool(result)

    return result


@dataclass
class DocStringArg:
    name: str
    type: str
    description: str


@dataclass
class DocStrings:
    main_description: str
    args: list[DocStringArg]


def get_docstrings(cls: type) -> DocStrings:
    main_description = inspect.getdoc(cls)
    args = []
    for field in fields(cls):
        typ = eval(field.type) if isinstance(field.type, str) else field.type
        if get_origin(typ) is Annotated:
            typ, metadata = get_args(typ)
        else:
            metadata = None
        args.append(DocStringArg(field.name, typ, metadata))
    return DocStrings(main_description, args)


def levenshtein_distance(string1, string2):
    n = len(string1)
    m = len(string2)
    d = [[0 for x in range(n + 1)] for y in range(m + 1)]

    for i in range(1, m + 1):
        d[i][0] = i

    for j in range(1, n + 1):
        d[0][j] = j

    for j in range(1, n + 1):
        for i in range(1, m + 1):
            if string1[j - 1] is string2[i - 1]:
                delta = 0
            else:
                delta = 1

            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + delta)

    return d[m][n]


def auto_fix_typos(
    expected_fields: list[str], actual_fields: dict[str, Any]
) -> dict[str, Any]:
    matched = {}
    expected = set(expected_fields)

    not_matched = []
    for k, v in actual_fields.items():
        if k in expected:
            matched[k] = v
            expected.remove(k)
        else:
            not_matched.append([k, v])
    for k, v in not_matched:
        if not expected:
            break
        closest = min(expected, key=lambda x: levenshtein_distance(x, k))
        matched[closest] = v
        expected.remove(closest)
    return matched


pattern: re.Pattern = re.compile(
    r"^```(?:json)?(?P<json>[^`]*)", re.MULTILINE | re.DOTALL
)


class RawJsonParser(BaseOutputParser):
    expected_keys: list[str] | None

    def parse(self, text: str) -> Any:
        logger.info(f"Raw JSON: {text}")
        if "```" in text:
            text = pattern.search(text).group("json")
        try:
            logger.info(f"Raw JSON: {text}")
            return cleaning_parse(text.replace("\\_", "_"), self.expected_keys)
        except yaml.YAMLError as e:
            msg = f"Failed to parse JSON from completion {text}. Got: {e}"
            raise OutputParserException(msg, llm_output=text) from e
        except Exception as e:
            msg = f"Failed to parse JSON from completion {text}. Got: {e}"
            raise OutputParserException(msg, llm_output=text) from e

    def get_format_instructions(self) -> str:
        return "Please return in JSON."


def ask_for_json(prompt: str, expected_keys: list[str] | None = None) -> Any:
    template = ChatPromptTemplate.from_template(prompt)
    llm = aux_llm()
    chain = template | llm | RawJsonParser(expected_keys=expected_keys)
    return chain.invoke({})


T = TypeVar("T")


def clean_null_values(d: dict) -> None:
    for k, v in d.items():
        if isinstance(v, dict):
            clean_null_values(v)
        elif v is None:
            del d[k]


def instantiate_instance(cls: type[T], data: dict) -> T:
    try:
        return cls(**data)
    except TypeError as e:
        logger.exception(f"Failed to instantiate {cls} with {data}. Got: {e}")
        docstring = get_docstrings(cls)
        buf = []
        args = docstring.args
        for arg in args:
            buf.append(f"// {arg.name}: {arg.description}")
            if arg.name in data:
                buf.append(yamlize({arg.name: data[arg.name]}).strip())
            else:
                buf.append(f"{arg.name}: UNSET // Please fill in")
        buf_joined = "\n".join(buf)
        prompt = (
            f"There is a YAML with some fields UNSET. Please fill out the UNSET fields in the YAML:\n"
            f"```\n"
            f"{buf_joined}\n"
            f"```\n"
            "Please return in YAML.\n"
        )
        yml = ask_for_json(prompt, [arg.name for arg in args])
        logger.info(f"Retried; Got {yml}")
        return cls(**yml)


class JsonParser(BaseOutputParser):
    cls: type
    predefined_args: dict = {}

    def parse(self, text: str) -> Any:
        logger.info(f"JsonParser: {text}")
        flds = fields(self.cls)
        if "```" in text:
            text = pattern.search(text).group("json")
        try:
            logger.info(f"JsonParser: {text}")
            data = cleaning_parse(text)
            if isinstance(data, dict):
                data = {k.replace(" ", "_"): v for k, v in data.items()}
                data = {k.lower(): v for k, v in data.items()}
                data = auto_fix_typos([f.name for f in flds], data)
                with_predefined_args = {**data, **self.predefined_args}
                return instantiate_instance(self.cls, with_predefined_args)
            else:
                try:
                    with_predefined_args = {**data, **self.predefined_args}
                    return instantiate_instance(self.cls, with_predefined_args)
                except TypeError:
                    if isinstance(data, list):
                        return [instantiate_instance(self.cls, x) for x in data]
        except json.JSONDecodeError as e:
            msg = f"Failed to parse JSON from completion {text}. Got: {e}"
            raise OutputParserException(msg, llm_output=text) from e
        except Exception as e:
            msg = f"Failed to parse {self.cls} from completion {text}. Got: {e}"
            raise OutputParserException(msg, llm_output=text) from e

    def get_format_instructions(self) -> str:
        return inst_for_struct(self.cls)


class Mythical(ABC):
    def make_context(self) -> str:
        docstrings = get_docstrings(self.__class__)
        flds = [
            f"{field.name}: {getattr(self, field.name)}"
            for field in fields(self.__class__)
        ]
        return f"{docstrings.main_description}\n" + "\n".join(flds)


T = TypeVar("T", bound=Mythical)


def generate_using_docstring(
    klass: type[T], args: dict, predefined_args: dict | None = None
) -> T:
    if predefined_args is None:
        predefined_args = {}
    llm = aux_llm()
    docstrings = get_docstrings(klass)
    prompt = "Generate me a "
    desc = list(" ".join(docstrings.main_description.split("\n")))
    desc[0] = desc[0].lower()
    prompt += "".join(desc)
    prompt += "\n"
    prompt += inst_for_struct(klass, ignore_set=set(predefined_args.keys()))
    template = render_template(prompt, {**args, **predefined_args})
    logger.info(f"Prompt: {prompt}")
    chain = (
        template
        | llm
        | OutputFixingParser.from_llm(
            parser=JsonParser(cls=klass, predefined_args=predefined_args), llm=llm
        )
    )
    return chain.with_retry().invoke({})


def typescriptize_type(typ: str | type) -> str:
    if is_dataclass(typ):
        # Assuming that they will be parsed from JSON string.
        return "string"
    if typ == str:
        return "string"
    if typ == int:
        return "number"
    if typ == float:
        return "number"
    if typ == bool:
        return "boolean"
    if not isinstance(typ, str) and get_origin(typ) is list:
        return f"{typescriptize_type(get_args(typ)[0])}[]"
    typ = typ.replace(" ", "").replace("'", "").replace('"', "")
    if typ.startswith("list"):
        return f"{typescriptize_type(typ[5:-1])}[]"
    if typ == "str":
        return "string"
    if typ == "int":
        return "number"
    if typ == "float":
        return "number"
    if typ == "bool":
        return "boolean"
    return typ


def inst_for_struct(klass, ignore_set: set[str] | None = None) -> str:
    if ignore_set is None:
        ignore_set = set()
    docstrings = get_docstrings(klass)
    prompt = ""
    prompt += "Fill out the following JSON object:\n"
    prompt += "```json\n"
    prompt += "{\n"
    for arg in docstrings.args:
        if arg.name in ignore_set:
            continue
        prompt += (
            f'"{arg.name}": // {typescriptize_type(arg.type)}, {arg.description}\n'
            if arg.description
            else f'"{arg.name}": // {typescriptize_type(arg.type)}\n'
        )
    prompt += "}\n"
    prompt += "```\n"
    prompt += "Please return a JSON object."
    logger.info(f"Prompt: {prompt}")
    return prompt


def make_str_of_value(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        if not value:
            return "N/A"
        return yaml.dump(value)
    if hasattr(value, "make_context") and "{" not in (ctxt := value.make_context()):
        return ctxt
    if is_dataclass(value):
        return yaml.dump(asdict(value))


def promptly(f=None, demangle: bool = True):
    """Decorate a function to make it use LLM to generate responses.

    The docstring should contain the following:
    ```
    {{formatting_instructions}}
    ```
    """
    if f is None:
        return partial(promptly, demangle=demangle)

    doc = inspect.getdoc(f)
    if doc is None:
        raise ValueError(f"Function {f} has no docstring.")
    if not re.search(r"{{\s*formatting_instructions\s*}}", doc):
        raise ValueError(
            f"Function {f} docstring {doc} does not contain {{formatting_instructions}}"
        )

    sig = inspect.signature(f)
    llm = aux_llm()

    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except Exception as e:
            raise ValueError(f"Failed to call {f} with {args} and {kwargs}") from e
        ba = sig.bind(*args, **kwargs)
        return_type = get_type_hints(f).get("return", inspect.Signature.empty)
        if return_type is inspect.Signature.empty:
            raise ValueError(f"Function {f} has no return type.")
        ctxt = []
        ba.apply_defaults()
        args = dict(ba.arguments.items())
        if args:
            ctxt.append("```yml")
            ctxt.append(yaml.dump(args))
            ctxt.append("```")
        input_str = "\n".join(ctxt)
        formatting_instructions = inst_for_struct(return_type)
        rest = (
            dict(
                **{k: make_str_of_value(v) for k, v in args.items()},
                **{f"_{k}": v for k, v in args.items()},
            )
            if not demangle
            else {
                **{k: v for k, v in args.items()},
            }
        )
        prompt = render_template(
            doc,
            {
                "input_yaml": input_str,
                "formatting_instructions": formatting_instructions,
                **rest,
            },
        )
        logger.info(f"Prompt: {prompt}")
        chain = prompt | llm | JsonParser(cls=return_type)
        return chain.invoke({})

    return wrapper


def sparkle(f):
    """Decorate a function to make it use LLM to generate responses."""
    doc = inspect.getdoc(f)
    if doc is None:
        raise ValueError(f"Function {f} has no docstring.")

    sig = inspect.signature(f)
    llm = aux_llm()

    @wraps(f)
    def wrapper(self, *args, **kwargs):
        # Check it calls.
        try:
            f(self, *args, **kwargs)
        except Exception as e:
            raise ValueError(f"Failed to call {f} with {args} and {kwargs}") from e
        ba = sig.bind(self, *args, **kwargs)
        return_type = get_type_hints(f).get("return", inspect.Signature.empty)
        if return_type is inspect.Signature.empty:
            raise ValueError(f"Function {f} has no return type.")
        ctxt = [f"Act as {self.make_context()}."]
        ba.apply_defaults()
        if "self" in args:
            del args["self"]
        if args:
            ctxt.append("You are given the following information:")
            args = dict(ba.arguments.items())
            ctxt.append("```yml")
            ctxt.append(yaml.dump(args))
            ctxt.append("```")
        ctxt.append(f"You job is to {doc}.")
        ctxt.append(inst_for_struct(return_type))
        prompt = ChatPromptTemplate.from_template("\n".join(ctxt))
        chain = prompt | llm | JsonParser(cls=return_type)
        ic(prompt)
        return chain.invoke({})

    return wrapper


@dataclass
class WriterArchetype:
    name: str
    tone: str
    register: str
    genres: list[str]

    @staticmethod
    def random() -> WriterArchetype:
        return random.choice(load_writer_archetypes())


@cache
def load_writer_archetypes() -> list[WriterArchetype]:
    with open("assets/writer_persona.toml") as f:
        parsed_data = tomlkit_to_popo(tomllib.load(f))
    return [WriterArchetype(**archetype) for archetype in parsed_data["writer"]]


@cache
def slurp_toml(path):
    with open(path) as f:
        return tomlkit_to_popo(tomllib.load(f))


def yamlize(item: object) -> str:
    if is_dataclass(item):
        return yaml.dump(item.__dict__)
    return yaml.dump(item)
