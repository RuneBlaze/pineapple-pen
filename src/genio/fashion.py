from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Annotated

from icecream import ic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from .base import Mythical, generate_using_docstring, sparkle
from .llm import aux_llm


def generate_inspiration_keywords():
    categories = {
        "natural_elements": ["water", "fire", "earth", "air", "stone", "wood"],
        "emotions": ["joy", "sorrow", "excitement", "calm", "fear", "hope"],
        "urban_scenes": [
            "cityscape",
            "street art",
            "neon lights",
            "subway",
            "cafes",
            "skyscrapers",
        ],
        "plants": ["roses", "orchids", "cacti", "bamboo", "fern", "ivy"],
        "animals": ["butterfly", "lion", "swan", "fox", "elephant", "owl"],
        "art_styles": [
            "abstract",
            "minimalist",
            "surreal",
            "pop art",
            "cubism",
            "art nouveau",
        ],
        "personal_life": [
            "family",
            "friendship",
            "love",
            "childhood",
            "adventure",
            "solitude",
        ],
    }
    keywords = [random.choice(categories[category]) for category in categories]
    return keywords


@dataclass
class SeasonConcept(Mythical):
    """A **guiding** concept for a fashion season designed for a specific brand.

    The executive designer is
    ```
    {{designer}}
    ```

    The brand concept is
    ```
    {{brand}}
    ```

    The designer has taken inspiration by the following keywords for this season:
    ```
    {{keywords}}
    ```
    """

    title: Annotated[
        str,
        "A public title suitable for PR and marketing for this fashion season for the brand.",
    ]
    tagline: str
    distinguishing_feature: Annotated[
        str,
        "A distinguishing feature of the season. One or two sentences, containing the color palette, concept.",
    ]
    business_goal: Annotated[
        str, "The business goal of the season. One or two sentences."
    ]

    @staticmethod
    def generate(designer: Designer, brand_concept: BrandConcept) -> SeasonConcept:
        keywords = generate_inspiration_keywords()
        return generate_using_docstring(
            SeasonConcept,
            {
                "designer": designer.make_context(),
                "brand": brand_concept.make_context(),
                "keywords": keywords,
            },
        )


@dataclass
class Designer(Mythical):
    """Designer profile of a business person specialized for {{speciality}} as if appearing in Vogue.
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
    """A line name with the core line idea, based on the brand: \n```\n{{description}}\n```\n. The brand name should be
    chic. This brand should distinguish itself from its competitors. Your writing will be a concept used for a light
    novel, but no need to lean towards stereotypical Japanese concepts."""

    brand_name: str
    design_principle: Annotated[
        str,
        "The core design principle of the brand, to write to designers and to design key KPIs. Two or three sentences.",
    ]
    negative_design: Annotated[
        str, "A brief description of what the brand is not. One or two sentences."
    ]
    one_line_pitch: Annotated[str, "A one-line pitch for the brand to the investors."]

    @staticmethod
    def generate(designer: Designer) -> BrandConcept:
        ctxt = designer.make_context()
        return generate_using_docstring(BrandConcept, {"description": ctxt})


@dataclass
class ResumeRatingResult:
    score: Annotated[
        int,
        "The score of the resume. A number between 1 and 10. 8 meaning good fit; 5 meaning borderline; 1 meaning not a fit at all.",
    ]
    reason: str

    def __post_init__(self):
        if not 1 <= self.score <= 10:
            raise ValueError(f"Score must be between 1 and 10: got {self.score}")


@dataclass
class CandidateResume:
    """A resume in the {{industry}} industry of a non-stereotypical candidate. Your writing will be unique, quirky,
    and creative, like a concept used for a light novel. This person's motivation and personality is deeply motivated
    by this secret: {{one_line_bio}}. This person might have just entered the industry and might not be an industry
    vet."""

    name: str
    age: float
    yoe: int
    alma_mater: str
    skills: Annotated[list[str], "A list of skills."]
    prior_experience: Annotated[str, "A brief description of the prior experience."]
    design_style: Annotated[str, "A brief description of the design style."]

    @staticmethod
    def generate(industry: str, one_line_bio: str | None = None) -> CandidateResume:
        llm = aux_llm()
        if not one_line_bio:
            chain = (
                ChatPromptTemplate.from_template(
                    "Generate a creative two-line secret and bio for some person. From all walks of life, can be young, can be old, but can be used almost as a two-sentence thriller/mystery novel, or the start of it."
                )
                | llm
                | StrOutputParser()
            )
            one_line_bio = chain.invoke({})
        return generate_using_docstring(
            CandidateResume, {"industry": industry, "one_line_bio": one_line_bio}
        )


@dataclass
class Recruiter(Mythical):
    """A recruiter hired for the brand \n```\n{{description}}\n```\n, based on all walks of life but highly motivated to become a recruiter. The concept is {{concept}}. Your writing will be creative, quirky, like a concept used for a light novel, but no need to lean towards stereotypical Japanese concepts."""

    name: str
    age: float
    recruiting_strategy: Annotated[
        str,
        "The strategy of the recruiter. A few sentences, and actionable and the types of candidates they are looking for.",
    ]
    candidate_quirk: Annotated[
        str,
        "Some words that would describe the hidden, secret quirk of the recruiter about the candidates they look for.",
    ]

    def make_context(self) -> str:
        return f"Recruiter {self.name} is a {self.age} year old recruiter, with the following recruiting strategy: {self.recruiting_strategy}."

    @staticmethod
    def generate(brand: BrandConcept, concept: str) -> Recruiter:
        ctxt = brand.make_context()
        return generate_using_docstring(
            Recruiter, {"description": ctxt, "concept": concept}
        )

    @sparkle
    def rate_resume(
        self, concept: BrandConcept, resume: CandidateResume
    ) -> ResumeRatingResult:
        """Rate a resume. How strong do you think this resume is, judging by the alignment
        to your recruitment philosophy and the company values. Use your best judgement. Weigh both pros and cons, and
        think step by step."""
        ...


designer = generate_using_docstring(Designer, {"speciality": "children's shoes"})
brand_concept = BrandConcept.generate(designer)
for _ in range(5):
    season_concept = ic(SeasonConcept.generate(designer, brand_concept))
# resumes = [CandidateResume.generate("fashion") for _ in range(5)]
# recruiter = ic(
#     Recruiter.generate(brand_concept, "a energetic cat-girl with a sweet-tooth")
# )
# for resume in resumes:
#     ic(resume)
#     ic(recruiter.rate_resume(brand_concept, resume))
