from __future__ import annotations
from dataclasses import dataclass
from typing import Annotated
from .base import Mythical, default_llm, generate_using_docstring, sparkle
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from icecream import ic



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
    """A line name with the core line idea, based on the brand: \n```\n{description}\n```\n. The brand name should be chic. This brand should distinguish itself from its competitors. Your writing will be a concept used for a light novel, but no need to lean towards stereotypical Japanese concepts."""
    
    brand_name: str
    design_principle: Annotated[str, "The core design principle of the brand, to write to designers and to design key KPIs. Two or three sentences."]
    negative_design: Annotated[str, "A brief description of what the brand is not. One or two sentences."]
    one_line_pitch: Annotated[str, "A one-line pitch for the brand to the investors."]

    @staticmethod
    def generate(designer: Designer) -> BrandConcept:
        ctxt = designer.make_context()
        return generate_using_docstring(BrandConcept, {"description": ctxt})
    

@dataclass
class ResumeRatingResult:
    score: Annotated[int, "The score of the resume. A number between 1 and 10. 8 meaning good fit; 5 meaning borderline; 1 meaning not a fit at all."]
    reason: str

    def __post_init__(self):
        if not 1 <= self.score <= 10:
            raise ValueError(f"Score must be between 1 and 10: got {self.score}")


@dataclass
class CandidateResume:
    """A resume in the {industry} industry of a non-stereotypical candidate. Your writing will be unique, quirky, and creative, like a concept used for a light novel. This person's motivation and personality is deeply motivated by this secret: {one_line_bio}"""

    name: str
    age: float
    yoe: int
    alma_mater: str
    skills: Annotated[list[str], "A list of skills."]
    prior_experience: Annotated[str, "A brief description of the prior experience."]
    design_style: Annotated[str, "A brief description of the design style."]

    @staticmethod
    def generate(industry: str, one_line_bio: str | None = None) -> CandidateResume:
        llm = default_llm()
        if not one_line_bio:
            chain = ChatPromptTemplate.from_template("Generate a creative two-line secret and bio for some person. From all walks of life, can be young, can be old, but can be used almost as a two-sentence thriller/mystery novel, or the start of it.") | llm | StrOutputParser()
            one_line_bio = chain.invoke({})
            ic(one_line_bio)
        return generate_using_docstring(CandidateResume, {"industry": industry, "one_line_bio": one_line_bio})

@dataclass
class Recruiter(Mythical):
    """A recruiter hired for the brand \n```\n{description}\n```\n, based on all walks of life but highly motivated to become a recruiter. The concept is {concept}. Your writing will be creative, quirky, like a concept used for a light novel, but no need to lean towards stereotypical Japanese concepts.
    """

    name: str
    age: float
    recruiting_strategy: Annotated[
        str, "The strategy of the recruiter. A few sentences, and actionable and the types of candidates they are looking for."
    ]

    @staticmethod
    def generate(brand: BrandConcept, concept: str) -> Recruiter:
        ctxt = brand.make_context()
        return generate_using_docstring(Recruiter, {"description": ctxt, "concept": concept})
    
    @sparkle
    def rate_resume(self, concept: BrandConcept, resume: CandidateResume) -> ResumeRatingResult:
        """Rate a resume. How strong do you think this resume is, judging by the alignment
        to your recruitment philosophy and the company values."""
        ...


for i in range(10):
    ic(CandidateResume.generate("fashion"))

# designer = generate_using_docstring(Designer, {"speciality": "children's shoes"})
# ic(designer)

# brand_concept = BrandConcept.generate(designer)
# ic(brand_concept)

# recruiter = Recruiter.generate(brand_concept, "a energetic cat-girl with a sweet-tooth")
# ic(recruiter)