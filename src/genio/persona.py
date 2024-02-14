from __future__ import annotations
from dataclasses import dataclass
from typing import Annotated
from genio.base import DocStringArg, Mythical, generate_using_docstring, sparkle
from langchain_community.chat_models import ChatOllama
import re

pattern: re.Pattern = re.compile(
    r"^```(?:ya?ml)?(?P<yaml>[^`]*)", re.MULTILINE | re.DOTALL
)


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
    def generate(designer: Designer) -> BrandConcept:
        ctxt = designer.make_context()
        return generate_using_docstring(BrandConcept, {"description": ctxt})
    

@dataclass
class DocStrings:
    main_description: str
    args: list[DocStringArg]


@dataclass
class ResumeRatingResult:
    score: Annotated[int, "The score of the resume. A number between 1 and 10. 8 meaning good fit; 5 meaning borderline; 1 meaning not a fit at all."]
    reason: str

    def __post_init__(self):
        if not 1 <= self.score <= 10:
            raise ValueError(f"Score must be between 1 and 10: got {self.score}")


@dataclass
class CandidateResume:
    # TODO: fill this out.
    ...


class Recruiter(Mythical):
    @staticmethod
    def generate() -> Recruiter:
        ...

    @sparkle
    def rate_resume(self, concept: BrandConcept, resume: CandidateResume) -> ResumeRatingResult:
        """Rate a resume. How strong do you think this resume is, judging by the alignment
        to your recruitment philosophy and the company values."""
        ...


designer = generate_using_docstring(Designer, {"speciality": "children's shoes"})
print(designer)

brand_concept = BrandConcept.generate(designer)
print(brand_concept)