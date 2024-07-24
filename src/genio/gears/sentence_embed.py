import numpy as np
from embeddings import KazumaCharEmbedding

KazumaCharEmbedding.url = "https://github.com/hassyGo/charNgram2vec/releases/download/v1.0.0-alpha/jmt_pre-trained_embeddings.tar.gz"


class SentenceEmbeddingGenerator:
    def __init__(self, model_name: str) -> None:
        self.model = KazumaCharEmbedding(model_name)

    def sentence_embedding(self, sentence: str) -> None:
        return np.array(self.model.emb(sentence))

    @staticmethod
    def default():
        return SentenceEmbeddingGenerator("wikipedia_gigaword")
