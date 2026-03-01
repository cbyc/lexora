import re


class SimpleChunker:
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self._chunk_size = chunk_size
        self._overlap = overlap
        # Sentence-ending patterns: period/question mark/exclamation followed by whitespace, or paragraph break.
        self._SENTENCE_BOUNDARY = re.compile(r"[.!?]\s|\n\n")

    def _find_split_point(self, text: str, start: int, end: int) -> int:
        """Find the best split point, preferring sentence then word boundaries.

        Searches backward from end within the last 20% of the chunk for a sentence
        boundary. If none is found, falls back to the nearest word boundary (space).
        If neither exists, returns the raw character offset.

        Args:
            text: The full document text.
            start: Start index of the current chunk.
            end: Raw end index (start + chunk_size).

        Returns:
            The adjusted end index for the chunk.
        """
        # If end is past the document, no need to search for a boundary.
        if end >= len(text):
            return len(text)

        # Search window: last 20% of the chunk.
        search_start = end - int(self._chunk_size * 0.2)
        if search_start < start:
            search_start = start

        window = text[search_start:end]

        # Find the last sentence boundary in the window (closest to end).
        sentence_matches = list(self._SENTENCE_BOUNDARY.finditer(window))
        if sentence_matches:
            # Use the last match — split right after the sentence-ending punctuation + space.
            return search_start + sentence_matches[-1].end()

        # Fall back to word boundary: find last space before end.
        last_space = text.rfind(" ", search_start, end)
        if last_space > start:
            return last_space + 1  # Split after the space.

        # No boundary found — split at raw character offset.
        return end

    def chunk(self, text: str) -> list[str]:
        """Split a text into overlapping text chunks.

        Prefers splitting at sentence boundaries, falling back to word boundaries,
        then raw character offsets. Each chunk is at most chunk_size characters.

        Args:
            text: The text to chunk.

        Returns:
            List of texts.
        """
        if not text:
            return []

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = start + self._chunk_size
            split_at = self._find_split_point(text, start, end)
            chunk_text = text[start:split_at]

            chunks.append(chunk_text)

            chunk_index += 1
            # If we've reached the end of the document, stop.
            if split_at >= len(text):
                break
            next_start = max(split_at - self._overlap, 0)
            # Ensure forward progress to avoid infinite loops.
            if next_start <= start:
                next_start = split_at
            start = next_start

        return chunks
