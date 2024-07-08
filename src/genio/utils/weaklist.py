from collections.abc import Iterable, Iterator, MutableSequence
from typing import TypeVar
from weakref import ref

T = TypeVar("T")


class WeakList(MutableSequence[T]):
    def __init__(self, iterable: Iterable[T] | None = None) -> None:
        self._list: list[ref[T]] = []
        if iterable is not None:
            self.extend(iterable)

    def __len__(self) -> int:
        return len(self._list)

    def __getitem__(self, index: int) -> T | None:
        return self._list[index]()

    def __setitem__(self, index: int, value: T) -> None:
        self._list[index] = ref(value)

    def __delitem__(self, index: int) -> None:
        del self._list[index]

    def insert(self, index: int, value: T) -> None:
        self._list.insert(index, ref(value))

    def __iter__(self) -> Iterator[T]:
        return (item() for item in self._list)

    def __contains__(self, item: T) -> bool:
        return any(item is ref() for ref in self._list)

    def __repr__(self) -> str:
        return repr([item() for item in self._list])

    def __str__(self) -> str:
        return str([item() for item in self._list])

    def garbage_collect(self) -> None:
        self._list = [ref for ref in self._list if ref() is not None]

    def append(self, value: T) -> None:
        self._list.append(ref(value))

    def extend(self, iterable: Iterable[T]) -> None:
        for value in iterable:
            self.append(value)

    def surviving_items(self) -> Iterator[T]:
        for item in self._list:
            if (it := item()) is not None:
                yield it
