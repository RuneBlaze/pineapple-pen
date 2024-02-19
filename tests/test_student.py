from genio.student import Archetype, Student, MemoryBank


def test_archetype_can_sample():
    assert Archetype.choice() is not None


def test_student_thingies():
    student = Student.generate_from_grade(1)
    assert student is not None
    memories = MemoryBank(student, 5)
    memories.witness_event("A cat died.")
    memories.witness_event("They found a new cat.")
