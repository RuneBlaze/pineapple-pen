from dataclasses import dataclass

import numpy as np


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


# model = SentenceTransformer("all-MiniLM-L6-v2")

# tar = tarfile.open(asset_path("cards.tar.gz"), "r:gz")

# documents = []
# for member in tar.getmembers():
#     f = tar.extractfile(member)
#     if f is not None:
#         if "._" in member.name:
#             continue
#         documents.append(stnp.load(f.read()))
#         break
# tar.close()

# documents = [SerializedCardArt(**d) for d in documents]

# document_vectors = np.array([d.embedding for d in documents])
