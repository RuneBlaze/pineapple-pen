from dataclasses import dataclass
from typing import Any, override

from genio.core.agent import ContextBuilder, ContextComponent
from genio.core.clock import Clock
from genio.core.memory import MemoryBank
from genio.core.student import StudentProfile


class ClockComponent(ContextComponent):
    clock: Clock

    @override
    def provides(self) -> dict[str, Any]:
        return {"clock": self.clock}

    @override
    def set_attribute(self, key: str, value: Any) -> None:
        match key:
            case "clock":
                self.clock = value
            case _:
                raise ValueError(f"Unknown attribute {key}")

    @override
    def build_context(self, re: str | None, builder: ContextBuilder) -> None:
        formatted_time = self.clock.state.strftime("%I:%M %p")
        builder.add_agenda(f"right now it is {formatted_time}")


class MemoryComponent(ContextComponent):
    memory_bank: MemoryBank

    @override
    def __post_attach__(self) -> None:
        self.memory_bank = MemoryBank(self.agent)

    @override
    def build_context(self, re: str | None, builder: ContextBuilder) -> None:
        memories = self.memory_bank.recall(re)
        for memory in memories:
            builder.add_memory(memory)

    @override
    def provides(self) -> dict[str, Any]:
        return {"memory": self.memory_bank}


@dataclass
class StudentProfileComponent(ContextComponent):
    student_profile: StudentProfile

    @override
    def build_context(self, re: str | None, builder: ContextBuilder) -> None:
        builder.add_identity(
            f"{self.student_profile.name}, age {self.student_profile.age}, grade {self.student_profile.grade}, {self.student_profile.height} CM tall"
        )
        builder.add_identity_pair("gender", self.student_profile.gender)
        builder.add_identity_pair("MBTI", self.student_profile.mbti_type)
        builder.add_identity(self.student_profile.bio)
