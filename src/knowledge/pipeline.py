from ports import AskAgent, Chunker, EmbeddingModel, DocumentStore
from knowledge.loaders.models import Document
from models import AskResponse, Chunk


class Pipeline:
    def __init__(
        self,
        chunker: Chunker,
        embedding_model: EmbeddingModel,
        document_store: DocumentStore,
        ask_agent: AskAgent,
    ):
        self._chunker = chunker
        self._embedding_model = embedding_model
        self._document_store = document_store
        self._ask_agent = ask_agent

    async def add_docs(self, docs: list[Document]):
        for doc in docs:
            chunks = []
            embeddings = []

            s = self._chunker.chunk(doc.content)
            for i, c in enumerate(s):
                chunks.append(Chunk(c, doc.source, i))
                embeddings.append(await self._embedding_model.encode(c))

            self._document_store.add_chunks(chunks, embeddings)

    async def search_document_store(self, query: str) -> list[Chunk]:
        query_embedding = await self._embedding_model.encode(query)
        result = self._document_store.search(query_embedding)
        return result

    async def ask(self, question: str) -> AskResponse:
        chunks = await self.search_document_store(question)
        return await self._ask_agent.answer(question, chunks)
