from src.ports import Chunker, EmbeddingModel, DocumentStore
from src.loaders.models import Document
from src.models import Chunk


class Pipeline:
    def __init__(
        self,
        chunker: Chunker,
        embedding_model: EmbeddingModel,
        document_store: DocumentStore,
    ):
        self._chunker = chunker
        self._embedding_model = embedding_model
        self._document_store = document_store

    def add_docs(self, docs: list[Document]):
        for doc in docs:
            chunks = []
            embeddings = []

            s = self._chunker.chunk(doc.content)
            for i, c in enumerate(s):
                chunks.append(Chunk(c, doc.source, i))
                embeddings.append(self._embedding_model.encode(c))

            self._document_store.add_chunks(chunks, embeddings)

    def search_document_store(self, query: str) -> list[Chunk]:
        query_embedding = self._embedding_model.encode(query)
        result = self._document_store.search(query_embedding)
        return result
