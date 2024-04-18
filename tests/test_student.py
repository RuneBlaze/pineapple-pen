import pytest
from genio.core.agent import MemoryBank
from genio.student import Archetype, StudentProfile


@pytest.mark.skip("takes too long")
def test_archetype_can_sample():
    assert Archetype.choice() is not None


def test_student_thingies():
    student = StudentProfile.generate_from_grade(1)
    assert student is not None
    memories = MemoryBank(student, 5)
    memories.witness_event("A cat died.")
    memories.witness_event("They found a new cat.")
