from __future__ import annotations

import inspect
import random
import re
from abc import ABC
from dataclasses import dataclass, fields
from functools import cache, wraps
from typing import Annotated, Any, Type, TypeVar, get_args, get_origin, get_type_hints

import tomlkit
import tomlkit as tomllib
import yaml
from icecream import ic
from langchain.output_parsers import OutputFixingParser
from langchain_community.chat_models import ChatOllama
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import ChatPromptTemplate

from .glueyaml import clean_yaml


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


@cache
def default_llm() -> ChatOllama:
    return ChatOllama(
        model="openhermes:7b-mistral-v2-q5_0", base_url="http://192.168.40.9:11434"
    )


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
        args.append(DocStringArg(field.name, field.type, metadata))
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
    # if len(actual_fields) < len(expected):
    # for
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
    r"^```(?:ya?ml)?(?P<yaml>[^`]*)", re.MULTILINE | re.DOTALL
)


class YamlParser(BaseOutputParser):
    cls: Type

    def parse(self, text: str) -> Any:
        if "```" in text:
            text = pattern.search(text).group("yaml")
        try:
            data = clean_yaml(text.replace("\\_", "_"))
            if isinstance(data, dict):
                data = {k.replace(" ", "_"): v for k, v in data.items()}
                data = {k.lower(): v for k, v in data.items()}
                data = auto_fix_typos([f.name for f in fields(self.cls)], data)
                return self.cls(**data)
            else:
                return self.cls(data)
        except yaml.YAMLError as e:
            msg = f"Failed to parse YAML from completion {text}. Got: {e}"
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


def generate_using_docstring(klass: Type[T], args: dict) -> T:
    llm = default_llm()
    docstrings = get_docstrings(klass)
    prompt = "Generate me a "
    desc = list(" ".join(docstrings.main_description.split("\n")))
    desc[0] = desc[0].lower()
    prompt += "".join(desc)

    prompt += "\n"
    prompt += inst_for_struct(klass)
    template = ChatPromptTemplate.from_template(prompt)

    chain = (
        template
        | llm
        | OutputFixingParser.from_llm(parser=YamlParser(cls=klass), llm=llm)
    )
    return chain.invoke(args)


def inst_for_struct(klass):
    docstrings = get_docstrings(klass)
    prompt = ""
    prompt += "It should contain the following YAML fields:\n"
    for arg in docstrings.args:
        prompt += (
            f"- {arg.name}: {arg.description}\n"
            if arg.description
            else f"- {arg.name}\n"
        )
    prompt += "Please return in YAML."
    return prompt


from dataclasses import asdict, is_dataclass


def make_str_of_value(value):
    if isinstance(value, str):
        return value
    if hasattr(value, "make_context"):
        return value.make_context()
    if is_dataclass(value):
        return yaml.dump(asdict(value))


def sparkle(f):
    """Decorate a function to make it use LLM to generate responses."""
    doc = inspect.getdoc(f)
    if doc is None:
        raise ValueError(f"Function {f} has no docstring.")

    sig = inspect.signature(f)
    llm = default_llm()

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
        ctxt.append("You are given the following information:")
        ctxt.append("```yml")
        for name, value in ba.arguments.items():
            if name == "self":
                continue
            value_str = make_str_of_value(value)
            ctxt.append(f"{name}: {value_str}")
        ctxt.append("```")
        ctxt.append(f"You job is to {doc}.")
        ctxt.append("Fill out the following:")
        ctxt.append(inst_for_struct(return_type))
        prompt = ChatPromptTemplate.from_template("\n".join(ctxt))
        ic(prompt)
        chain = prompt | llm | YamlParser(cls=return_type)
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
    with open("assets/writer_persona.toml", "r") as f:
        parsed_data = tomlkit_to_popo(tomllib.load(f))
    return [WriterArchetype(**archetype) for archetype in parsed_data["writer"]]


def slurp_toml(path):
    with open(path, "r") as f:
        return tomlkit_to_popo(tomllib.load(f))
