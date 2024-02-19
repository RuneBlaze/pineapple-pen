from functools import cache
from sentence_transformers import SentenceTransformer


@cache
def get_embedding_model():
    return SentenceTransformer("all-MiniLM-L6-v2")


def embed_sentences(sentences: list[str]):
    return get_embedding_model().encode(sentences)


def embed_single_sentence(sentence: str):
    return embed_sentences([sentence])[0]


if __name__ == "__main__":
    print(type(embed_single_sentence("Hello, world!")))
