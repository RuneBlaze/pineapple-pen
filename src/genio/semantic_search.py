import tarfile
from dataclasses import dataclass
from functools import cache

import numpy as np
import safetensors.numpy as stnp
from sentence_transformers import SentenceTransformer

from genio.base import asset_path


def fix_palette(quantized_image):
    correct_mapping = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 11, 12, 14, 15]
    inverse = np.argsort(correct_mapping)

    # Create a new array with corrected indices
    corrected_quantized_image = np.zeros_like(quantized_image)

    for i in range(len(inverse)):
        corrected_quantized_image[quantized_image == i] = correct_mapping[i]

    return corrected_quantized_image


@dataclass
class SerializedCardArt:
    faded: np.ndarray
    unfaded: np.ndarray
    prompt: str
    embedding: np.ndarray

    def __post_init__(self):
        self.prompt = self.prompt.view(f"S{self.prompt.shape[0]}")
        self.faded = fix_palette(self.faded)
        self.unfaded = fix_palette(self.unfaded)


model = SentenceTransformer("all-MiniLM-L6-v2")

tar = tarfile.open(asset_path("cards.tar.gz"), "r:gz")

documents = []
for member in tar.getmembers():
    f = tar.extractfile(member)
    if f is not None:
        if "._" in member.name:
            continue
        documents.append(stnp.load(f.read()))
        break
tar.close()

documents = [SerializedCardArt(**d) for d in documents]

document_vectors = np.array([d.embedding for d in documents])


@cache
def _search_closest_document(sentence: str) -> dict:
    sentence_embedding = model.encode(sentence)
    similarities = np.dot(document_vectors, sentence_embedding)
    idx = np.argmax(similarities)
    return {"index": idx, "similarity": similarities[idx]}


def search_closest_document(sentence: str) -> SerializedCardArt:
    # FIXME: this feature is deprecated, so returning the first document for now.
    return documents[0]


if __name__ == "__main__":
    while True:
        sentence = input("Enter a sentence: ")
        if sentence == "exit":
            break
        result = _search_closest_document(sentence)
        print(
            f"Most similar document: {result['index']} with similarity {result['similarity']}"
        )
        print(documents[result["index"]].prompt)
