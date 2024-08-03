from typing import Any
import numpy as np
from embeddings import KazumaCharEmbedding
import hnswlib
from typing import Generic, TypeVar

KazumaCharEmbedding.url = "https://github.com/hassyGo/charNgram2vec/releases/download/v1.0.0-alpha/jmt_pre-trained_embeddings.tar.gz" # DIM 100


class SentenceEmbeddingGenerator:
    def __init__(self, model_name: str) -> None:
        self.model = KazumaCharEmbedding(model_name)

    def sentence_embedding(self, sentence: str) -> np.ndarray:
        return np.array(self.model.emb(sentence))
    
    def embed(self, sentence: str) -> np.ndarray:
        return self.sentence_embedding(sentence)

    @staticmethod
    def default():
        return SentenceEmbeddingGenerator("wikipedia_gigaword")

T = TypeVar("T")

class Corpus(Generic[T]):
    def __init__(self, strings: list[str], userdata: list[T] | None = None) -> None:
        if not userdata:
            userdata = [None] * len(strings)
        dim = 100
        num_elements = len(strings)

        p = hnswlib.Index(space='l2', dim=dim)
        p.init_index(max_elements=num_elements, ef_construction=200, M=16)

        gen = SentenceEmbeddingGenerator.default()
        embeddings = np.stack([gen.sentence_embedding(s) for s in strings])
        ids = np.arange(num_elements)
        p.add_items(embeddings, ids)
        p.set_ef(10)

        self.index = p
        self.strings = strings
        self.userdata = userdata

        self.search_cache = {}
    
    def _search(self, query: str) -> tuple[str, T]:
        gen = SentenceEmbeddingGenerator.default()
        query_embedding = gen.sentence_embedding(query)
        labels, _ = self.index.knn_query(query_embedding, k=1)
        return self.strings[labels[0][0]], self.userdata[labels[0][0]]
    
    def search(self, query: str) -> tuple[str, T]:
        if query in self.search_cache:
            return self.search_cache[query]
        result = self._search(query)
        self.search_cache[query] = result
        return result
