class SimpleChunker:
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk(self, text: str) -> list[str]:
        chunks = []

        step = self._chunk_size - self._overlap
        for i in range(0, len(text), step):
            chunk = text[i : i + self._chunk_size]
            chunks.append(chunk)

            # Stop if we've reached the end of the text
            if i + self._chunk_size >= len(text):
                break

        return chunks
