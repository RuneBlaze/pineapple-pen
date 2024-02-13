from abc import ABC
from yaml import safe_load
from dataclasses import dataclass, fields
import yaml
import inspect
from typing import TypeVar

from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.exceptions import OutputParserException
from genio.persona import DocStrings, pattern
from typing import Annotated, Any, Type, get_args, get_origin


@dataclass
class DocStringArg:
    name: str
    type: str
    description: str


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


class Mythical(ABC):

    def make_context(self) -> str:
        docstrings = get_docstrings(self.__class__)
        flds = [f"{field.name}: {getattr(self, field.name)}" for field in fields(self.__class__)]
        return f"{docstrings.main_description}\n" + "\n".join(flds)


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


T = TypeVar("T", bound=Mythical)
def generate_using_docstring(llm, klass: Type[T], args: dict) -> T:
    docstrings = get_docstrings(klass)
    prompt = "Generate me a "
    desc = list(' '.join(docstrings.main_description.split("\n")))
    desc[0] = desc[0].lower()
    prompt += ''.join(desc)

    prompt += "\n"
    prompt += inst_for_struct(klass)
    template = ChatPromptTemplate.from_template(prompt)
    chain = template | llm | YamlParser(cls=klass)
    return chain.invoke(args)


def inst_for_struct(klass):
    docstrings = get_docstrings(klass)
    prompt = ""
    prompt += "It should contain the following information:\n"
    for arg in docstrings.args:
        prompt += f"- {arg.name}: {arg.description}\n" if arg.description else f"- {arg.name}\n"
    prompt += "Please return in YAML."
    return prompt