import random
from dataclasses import dataclass
from typing import Annotated, Literal, TypeAlias

import pandas as pd
import streamlit as st

from genio.core.base import access, promptly, slurp_toml
from genio.tools import Card, CardType, EnemyBattler

predef = slurp_toml("assets/strings.toml")

LogType: TypeAlias = tuple[Literal["user", "them", "narrator", "system"], str]


def parse_card_description(description: str) -> tuple[str, str, int]:
    # Split on the '#' to separate the main part from the description
    parts = description.split("#")
    main_part = parts[0].strip()
    desc = parts[1].strip() if len(parts) > 1 else None

    # Check for the '*' to determine the number of copies
    if "*" in main_part:
        name, copies_str = main_part.split("*")
        name = name.strip()
        copies = int(copies_str.strip())
    else:
        name = main_part
        copies = 1

    return name, desc, copies


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
        name, desc, copies = parse_card_description(card_description)
        card_type = determine_card_type(name)
        for _ in range(copies):
            deck.append(Card(card_type=card_type, name=name, description=desc))
    return deck


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
    {% include('judge.md') %}

    {{ formatting_instructions }}
    """
    ...


default_conversation_context = """\
It's a brightly lit restaurant, sparsely populated with a few patrons.

Jon: "I'm so glad you could make it. I've been looking forward to this all week."
[FILL IN]
"""

# starter_enemy = TalkingProfile.from_predef("enemies.starter")
# starter_player = TalkingProfile.from_predef("players.starter")

# completed = _complete_sentence(
#     words=["*talk about*", "'love'", "'money'"],
#     user=starter_player,
#     other=starter_enemy,
#     conversation_context=default_conversation_context,
# )

# st.write(completed)

enemy = EnemyBattler.from_predef("enemies.slime")
st.json(
    {
        "hp": enemy.hp,
        "max_hp": enemy.max_hp,
        "shield_points": enemy.shield_points,
        "name": enemy.profile.name,
    }
)


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
deck_df = pd.DataFrame([card.to_record() for card in st.session_state.deck])
graveyard_df = pd.DataFrame([card.to_record() for card in st.session_state.graveyard])

with st.expander("Deck"):
    st.dataframe(deck_df)

with st.expander("Graveyard"):
    st.dataframe(graveyard_df)
