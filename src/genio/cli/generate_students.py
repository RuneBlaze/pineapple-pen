import random

import typer
import yaml

from genio.core.student import (
    Student,
    generate_student,
    populate_appearances_matrix,
    upgrade_to_friendship,
)


def non_diagonal_entries(n: int) -> list[tuple[int, int]]:
    return [(i, j) for i in range(n) for j in range(n) if i != j]


def upgrade_friendship(students: list[Student], i: int, j: int) -> None:
    students[i].appearance_view[students[j]] = upgrade_to_friendship(
        students[i], students[j]
    )


def main(
    n: int = typer.Option(..., help="Number of students to generate"),
    output: str = typer.Option(..., help="Output file"),
):
    students = [generate_student(4) for _ in range(n)]
    populate_appearances_matrix(students)
    ents = non_diagonal_entries(n)
    two_pairs = random.sample(ents, 2)
    for i, j in two_pairs:
        upgrade_friendship(students, i, j)
    data = {"students": students}
    with open(output, "w") as f:
        yaml.dump(data, f)


if __name__ == "__main__":
    typer.run(main)
