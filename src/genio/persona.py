from __future__ import annotations
from dataclasses import dataclass, fields
from abc import ABC
import inspect
from typing import Any, Type, Annotated, get_origin, get_args

from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.exceptions import OutputParserException
import re

pattern: re.Pattern = re.compile(
    r"^```(?:ya?ml)?(?P<yaml>[^`]*)", re.MULTILINE | re.DOTALL
)

from yaml import safe_load, safe_dump
import yaml


class Mythical(ABC):

    def make_context(self) -> str:
        docstrings = get_docstrings(self.__class__)
        flds = [f"{field.name}: {getattr(self, field.name)}" for field in fields(self.__class__)]
        return f"{docstrings.main_description}\n" + "\n".join(flds)

@dataclass
class Designer(Mythical):
    """Designer profile of a business person specialized for {speciality} as if appearing in Vogue.
    Your writing will be a concept used for a light novel, but not using stereotypical Japanese words.
    """

    name: str
    age: float
    bio: Annotated[str, "A brief bio of the person in no more than four sentences."]
    design_concept: Annotated[
        str,
        "A very brief description in no more than four sentences including their artistic statement.",
    ]


@dataclass
class BrandConcept(Mythical):
    """Given this founder of the brand: \n```\n{description}\n```\n. Generate me a line name with the core line idea. The brand name should be chic. This brand should distinguish itself from its competitors. Your writing will be a concept used for a light novel, but no need to lean towards stereotypical Japanese concepts."""
    
    brand_name: str
    design_principle: Annotated[str, "The core design principle of the brand, to write to designers and to design key KPIs. Two or three sentences."]
    negative_design: Annotated[str, "A brief description of what the brand is not. One or two sentences."]
    one_line_pitch: Annotated[str, "A one-line pitch for the brand to the investors."]

    @staticmethod
    def generate(llm, designer: Designer) -> BrandConcept:
        ctxt = designer.make_context()
        return generate_using_docstring(llm, BrandConcept, {"description": ctxt})
    

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
        typ = eval(field.type)
        if get_origin(typ) is Annotated:
            typ, metadata = get_args(typ)
        else:
            metadata = None
        args.append(DocStringArg(field.name, field.type, metadata))
    return DocStrings(main_description, args)


def generate_using_docstring(llm, klass: Type[Mythical], args: dict) -> Mythical:
    docstrings = get_docstrings(klass)
    prompt = "Generate me a "
    desc = list(' '.join(docstrings.main_description.split("\n")))
    desc[0] = desc[0].lower()
    prompt += ''.join(desc)
    
    prompt += "\n"
    prompt += "It should contain the following information:\n"
    for arg in docstrings.args:
        prompt += f"- {arg.name}: {arg.description}\n" if arg.description else f"- {arg.name}\n"
    prompt += "Please return in YAML."

    template = ChatPromptTemplate.from_template(prompt)
    chain = template | llm | YamlParser(cls=klass)
    return chain.invoke(args)


@dataclass
class ResumeRatingResult:
    score: Annotated[int, "The score of the resume. A number between 1 and 10. 8 meaning good fit; 5 meaning borderline; 1 meaning not a fit at all."]
    reason: str

    def __post_init__(self):
        if not 1 <= self.score <= 10:
            raise ValueError(f"Score must be between 1 and 10: got {self.score}")


class Recruiter(Mythical):
    @staticmethod
    def generate() -> Recruiter:
        ...

    def rate_resume() -> RatingResult:


class YamlParser(BaseOutputParser):
    cls: Type

    def parse(self, text: str) -> Any:
        if "```" in text:
            text = pattern.search(text).group("yaml")
        text.replace(":\n", ": ")
        try:
            data = safe_load(text.replace("\\_", "_"))
            data = {k.replace(" ", "_"): v for k, v in data.items()}
            data = {k.lower(): v for k, v in data.items()}
            return self.cls(**data)
        except yaml.YAMLError as e:
            msg = f"Failed to parse YAML from completion {text}. Got: {e}"
            raise OutputParserException(msg, llm_output=text) from e
        except Exception as e:
            msg = f"Failed to parse {self.cls} from completion {text}. Got: {e}"
            raise OutputParserException(msg, llm_output=text) from e

llm = ChatOllama(model="mistral:7b-instruct-q5_0")

designer = generate_using_docstring(llm, Designer, {"speciality": "children's shoes"})
print(designer)

brand_concept = BrandConcept.generate(llm, designer)
print(brand_concept)