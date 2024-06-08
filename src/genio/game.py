import random
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Literal, TypeAlias

import pandas as pd
import streamlit as st

from genio.core.base import access, promptly, slurp_toml

predef = slurp_toml("assets/strings.toml")

LogType: TypeAlias = tuple[Literal["user", "them", "narrator", "system"], str]


class CardType(Enum):
    CONCEPT = "concept"
    ACTION = "action"
    SPECIAL = "special"


@dataclass
class CompletedSentence:
    """A completed sentence in the game. An occurrence, a line, of the game's narrative."""

    reason: Annotated[
        str,
        "Justification for the completion. How the *action* connects the concepts serially.",
    ]
    sentence: Annotated[
        str,
        "A sentence or two that continues the current scenario, uses the action, and connects the concepts.",
    ]


@dataclass
class TalkingProfile:
    name: str
    profile: str

    @staticmethod
    def from_predef(key: str) -> "TalkingProfile":
        return TalkingProfile(**access(predef, key))


@promptly
def _complete_sentence(
    words: list[str],
    user: TalkingProfile,
    other: TalkingProfile,
    conversation_context: str,
) -> CompletedSentence:
    """\
    {% include('templates.form_sentence') %}

    {{ formatting_instructions }}
    """
    ...


default_conversation_context = """\
It's a brightly lit restaurant, sparsely populated with a few patrons.

Jon: "I'm so glad you could make it. I've been looking forward to this all week."
[FILL IN]
"""

starter_enemy = TalkingProfile.from_predef("enemies.starter")
starter_player = TalkingProfile.from_predef("players.starter")

completed = _complete_sentence(
    words=["*talk about*", "'love'", "'money'"],
    user=starter_player,
    other=starter_enemy,
    conversation_context=default_conversation_context,
)

st.write(completed)


@dataclass
class Card:
    card_type: CardType
    name: str
    score: tuple[Literal["x", "+"], int] | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


def parse_card_description(description: str) -> tuple[str, int]:
    match = re.match(
        r"(.*?)(?:\s*\(\+(\d+)\)|\s*\((x\d+)\))?\s*\*\s*(\d+)?", description
    )
    if match:
        name = match.group(1).strip()
        score = None
        if match.group(2):
            score = ("+", int(match.group(2)))
        elif match.group(3):
            score = ("x", int(match.group(3)[1:]))
        copies = int(match.group(4)) if match.group(4) else 1
        return name, score, copies
    else:
        return description.strip(), None, 1


def determine_card_type(name: str) -> CardType:
    if name[0].islower():
        return CardType.CONCEPT
    elif name[0].isupper():
        return CardType.ACTION
    else:
        return CardType.SPECIAL


def create_deck(cards: list[str]) -> list[Card]:
    deck = []
    for card_description in cards:
        name, score, copies = parse_card_description(card_description)
        card_type = determine_card_type(name)
        for _ in range(copies):
            deck.append(Card(card_type=card_type, name=name, score=score))
    return deck


@dataclass
class GameScores:
    enemy_romance_value: int
    enemy_romance_value_target: int
    enemy_sanity: int

    money: int
    time: int
    player_sanity: int
    player_health: int = 5


# Function to draw cards from the deck
def draw_cards(deck: list[Card], num_cards: int) -> list[Card]:
    if len(deck) < num_cards:
        num_cards = len(deck)
    return random.sample(deck, num_cards)


# Function to get color for a card
def get_card_color(card: Card, colors: dict[str, str]) -> str:
    return colors[card.card_type.value]


# Initialize session state for deck, hand, graveyard, and log
if "deck" not in st.session_state:
    st.session_state.deck = create_deck(predef["initial_deck"]["cards"])
    st.session_state.hand = draw_cards(st.session_state.deck, 6)
    st.session_state.graveyard = []
    st.session_state.log = []
    st.session_state.scores = GameScores(
        enemy_romance_value=0,
        enemy_romance_value_target=100,
        enemy_sanity=3,
        money=10,
        time=5,
        player_sanity=5,
    )

# Define colors for each card type
colors = {
    "concept": "darkcyan",
    "action": "mediumpurple",
    "special": "tan",
}

with st.sidebar:
    st.header("Game Info")
    st.subheader("Enemy")
    st.text(
        f"❤️‍🔥 : {st.session_state.scores.enemy_romance_value} / {st.session_state.scores.enemy_romance_value_target}"
    )
    st.progress(
        st.session_state.scores.enemy_romance_value
        / st.session_state.scores.enemy_romance_value_target
    )
    st.text(f"Enemy 💔 : {st.session_state.scores.enemy_sanity}")

    st.subheader("Player")
    st.text(f"💰 : {st.session_state.scores.money}")
    st.text(f"⏳ : {st.session_state.scores.time}")
    st.text(f"Player 🧠 : {st.session_state.scores.player_sanity}")


with st.container(border=True):
    # Display the game log using a chat interface
    st.subheader("Game Log")
    avatars = {
        "user": "👤",
        "them": "👥",
        "narrator": "📣",
        "system": "💻",
    }
    for who, log_entry in st.session_state.log:
        st.chat_message("assistant", avatar=avatars[who]).write(log_entry)

# Display the hand and allow selection of cards to play
hand_names = [card.name for card in st.session_state.hand]
selection = st.multiselect("Pick cards to play", hand_names, key="multiselect")

# Button to play the selected cards
if st.button("Play hand"):
    st.text("Cards played:")
    for selected_card in selection:
        st.info(selected_card)
        # Remove played cards from the hand and add to graveyard
        played_cards = [
            card for card in st.session_state.hand if card.name in selection
        ]
        st.session_state.graveyard.extend(played_cards)
        st.session_state.hand = [
            card for card in st.session_state.hand if card.name not in selection
        ]
        st.session_state.log.append(("user", f"Played: {selected_card}"))

    # Discard current hand and draw new hand
    if len(st.session_state.deck) < 6:
        # If deck is empty, shuffle graveyard into deck
        st.session_state.deck.extend(st.session_state.graveyard)
        st.session_state.graveyard = []
        with st.chat_message("system") as message:
            message.write("Shuffled graveyard into deck")

    st.session_state.hand = draw_cards(st.session_state.deck, 6)
    st.session_state.deck = [
        card for card in st.session_state.deck if card not in st.session_state.hand
    ]
    st.rerun()

# Display the current hand
st.text("Current Hand:")
for card in st.session_state.hand:
    color = get_card_color(card, colors)
    st.markdown(
        f"<span style='background-color:{color};padding:5px;border-radius:5px;'>{card.name} ({card.card_type.value.capitalize()})</span>",
        unsafe_allow_html=True,
    )

# Display deck and graveyard as dataframes
deck_df = pd.DataFrame(
    [
        {"ID": card.id, "Name": card.name, "Type": card.card_type.value}
        for card in st.session_state.deck
    ]
)
graveyard_df = pd.DataFrame(
    [
        {"ID": card.id, "Name": card.name, "Type": card.card_type.value}
        for card in st.session_state.graveyard
    ]
)

with st.expander("Deck"):
    st.dataframe(deck_df)

with st.expander("Graveyard"):
    st.dataframe(graveyard_df)
