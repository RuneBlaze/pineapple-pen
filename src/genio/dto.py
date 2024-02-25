from __future__ import annotations
from pydantic.dataclasses import dataclass
from .architect import (
    InteriorDesignGuidelines,
    ArchitecturalGuidelines,
    SchoolConcept,
    ClassRef,
    SingleFloorConcept,
    ConceptPacket,
    TriConcept,
)
import pickle as pkl


@dataclass
class RoomDocket:
    name: str
    classref: ClassRef | None
    tri_concept: TriConcept


@dataclass
class FloorDocket:
    title: str
    rooms: list[RoomDocket]

    @staticmethod
    def from_generated(
        concept: SingleFloorConcept, tri_concepts: list[TriConcept]
    ) -> FloorDocket:
        return FloorDocket(
            title=concept.floor_title,
            rooms=[
                RoomDocket(
                    name=tri_concept.name,
                    classref=tri_concept.classref,
                    tri_concept=tri_concept,
                )
                for tri_concept in tri_concepts
            ],
        )


@dataclass
class SchoolDocket:
    floors: list[FloorDocket]
    concept: SchoolConcept
    interior_guidelines: InteriorDesignGuidelines
    architectural_guidelines: ArchitecturalGuidelines

    @staticmethod
    def from_concept_packet(concept_packet: ConceptPacket) -> SchoolDocket:
        return SchoolDocket(
            concept=concept_packet.school_concept,
            interior_guidelines=concept_packet.interior_guidelines,
            architectural_guidelines=concept_packet.architectural_guidelines,
            floors=[
                FloorDocket.from_generated(concept, tri_concepts)
                for (concept, _), tri_concepts in zip(
                    concept_packet.concepts_and_catalogues, concept_packet.floor_rooms
                )
            ],
        )


if __name__ == "__main__":
    with open("assets/test.pkl", "rb") as f:
        concept_packet = pkl.load(f)
    docket = SchoolDocket.from_concept_packet(concept_packet)
