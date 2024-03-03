import tantivy

# Declaring our schema.
schema_builder = tantivy.SchemaBuilder()
schema_builder.add_text_field("title", stored=True, tokenizer_name="en_stem")
schema_builder.add_text_field("body", stored=True, tokenizer_name="en_stem")
schema = schema_builder.build()

index = tantivy.Index(schema)
writer = index.writer()
writer.add_document(
    tantivy.Document(
        title=["The Old man and the sea"],
        body=[
            """He was an old man who fished alone in a skiff in the Gulf Stream and he had gone eighty-four days now without taking a fish."""
        ],
    )
)
# ... and committing
writer.commit()

index.reload()
searcher = index.searcher()
query = index.parse_query("old", ["title", "body"])
(best_score, best_doc_address) = searcher.search(query, 3).hits[0]
best_doc = searcher.doc(best_doc_address)
print(best_doc["title"])
