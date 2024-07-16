import ahocorasick

PASTEL_COLORS = """
#f0c297
#cf968c
#8f5765
#c7d4e1
#928fb8
#5b537d
#c6d831
#77b02a
#429058
#f5a15d
#d46453
#9c3247
#ff7a7d
#ff417d
#d61a88
#b0fff1
#78d7ff
#488bd4
""".split()


class NameHighlighter:
    def __init__(self, names: list[str]) -> None:
        self.names = names
        self.automaton = self._create_automaton(names)

    @staticmethod
    def _create_automaton(names: list[str]) -> ahocorasick.Automaton:
        """Create and return an Aho-Corasick automaton from the given names."""
        automaton = ahocorasick.Automaton()
        for i, name in enumerate(names):
            for part in name.split():
                automaton.add_word(part, (i, part))
            automaton.add_word(name, (i, name))
        automaton.make_automaton()
        return automaton

    def label_text(self, text: str) -> tuple[str, set[int]]:
        matches = self._find_matches(text)
        compacted_matches = self._compact_matches(matches)
        return self._replace_text(text, compacted_matches), set(
            i for _, _, i in compacted_matches
        )

    def _find_matches(self, text: str) -> list:
        """Find matches in the text using the automaton."""
        matches = []
        for end_index, (i, original_value) in self.automaton.iter(text):
            start_index = end_index - len(original_value) + 1
            matches.append((start_index, end_index, i))
        return matches

    def _compact_matches(self, matches: list) -> list:
        """Compact the matches to avoid overlaps."""
        compacted = []
        for match in matches:
            if not compacted or self._is_non_overlapping(match, compacted[-1]):
                compacted.append(match)
        return compacted

    @staticmethod
    def _is_non_overlapping(current_match, last_match) -> bool:
        """Determine if the current match is non-overlapping with the last match."""
        _, last_end, last_i = last_match
        start, end, i = current_match
        return (start > last_end) or (i != last_i and start == last_end)

    def _replace_text(self, text: str, matches: list) -> str:
        """Replace matched text segments with highlighted versions."""
        offset = 0
        for start, end, i in matches:
            color = PASTEL_COLORS[(i * 3) % len(PASTEL_COLORS)]
            original_value = text[start + offset : end + 1 + offset]
            replaced = f"[{color}]{original_value}[/{color}]"
            text = text[: start + offset] + replaced + text[end + 1 + offset :]
            offset += len(replaced) - len(original_value)
        return text
