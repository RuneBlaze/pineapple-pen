from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

import tantivy


@cache
def global_factual_storage():
    return TantivyStore()


@dataclass
class FactualEntry:
    title: str | None
    body: str

    def __post_init__(self):
        if not self.title:
            self.title = None

    def to_context(self) -> str:
        if self.title:
            return f"""about "{self.title}": {self.body}"""
        return self.body


class TantivyStore:
    @staticmethod
    @cache
    def schema():
        schema_builder = tantivy.SchemaBuilder()
        schema_builder.add_text_field("title", stored=True, tokenizer_name="en_stem")
        schema_builder.add_text_field("body", stored=True, tokenizer_name="en_stem")
        schema_builder.add_text_field("keywords", stored=True, tokenizer_name="en_stem")
        return schema_builder.build()

    def __init__(self, parent: TantivyStore | None = None) -> None:
        self.index = tantivy.Index(self.schema())
        self.writer = self.index.writer()
        self.parent = parent
        self.entries = []

    def __reduce__(self):
        return TantivyStore.from_documents, (self.entries, self.parent is None)

    @staticmethod
    def from_documents(docs: list[dict], is_global_store: bool) -> TantivyStore:
        if is_global_store:
            store = global_factual_storage()
        else:
            store = TantivyStore(global_factual_storage())
        for doc in docs:
            store.insert(doc["title"], doc["body"], doc["keywords"])
        return store

    def recall(self, topic: str, top_k: int = 1) -> list[FactualEntry]:
        self.index.reload()
        try:
            query = self.index.parse_query(topic, ["title", "body", "keywords"])
        except ValueError:
            topic = re.sub("[^0-9a-zA-Z]+", " ", topic)
            query = self.index.parse_query(topic, ["title", "body", "keywords"])
        searcher = self.index.searcher()
        hits = searcher.search(query, top_k).hits
        res = []
        if self.parent:
            res += self.parent.recall(topic, top_k)
        for hit in hits:
            score, doc_address = hit
            doc = searcher.doc(doc_address)
            res.append(FactualEntry(doc["title"][0], doc["body"][0]))
        return res

    def recall_one(self, topic: str) -> FactualEntry | None:
        res = self.recall(topic)
        return res[0] if res else None

    def insert(self, title: str | None, body: str, keywords: str | None = None) -> None:
        title = title or ""
        keywords = keywords or ""
        self.writer.add_document(
            tantivy.Document(body=[body], title=[title], keywords=[keywords])
        )
        self.entries.append({"title": title, "body": body, "keywords": keywords})
        self.writer.commit()
