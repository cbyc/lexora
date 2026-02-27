"""Tests for SimpleChunker."""

from src.knowledge.chunker import SimpleChunker


class TestSimpleChunker:
    def test_returns_list_of_strings(self):
        """chunk should return a list of strings."""
        chunker = SimpleChunker(chunk_size=10, overlap=2)
        result = chunker.chunk("some text here")
        assert isinstance(result, list)
        assert all(isinstance(c, str) for c in result)

    def test_short_text_returns_single_chunk(self):
        """Text shorter than chunk_size should return a single chunk."""
        chunker = SimpleChunker(chunk_size=100, overlap=10)
        result = chunker.chunk("hello world")
        assert result == ["hello world"]

    def test_text_equal_to_chunk_size_returns_single_chunk(self):
        """Text exactly chunk_size long should return a single chunk."""
        chunker = SimpleChunker(chunk_size=5, overlap=1)
        result = chunker.chunk("hello")
        assert result == ["hello"]

    def test_empty_text_returns_empty_list(self):
        """Empty input should return an empty list."""
        chunker = SimpleChunker(chunk_size=10, overlap=2)
        result = chunker.chunk("")
        assert result == []

    def test_long_text_produces_multiple_chunks(self):
        """Text longer than chunk_size should produce more than one chunk."""
        chunker = SimpleChunker(chunk_size=5, overlap=1)
        result = chunker.chunk("0123456789")
        assert len(result) > 1

    def test_full_chunks_respect_chunk_size(self):
        """Every chunk except possibly the last should be exactly chunk_size characters."""
        chunker = SimpleChunker(chunk_size=5, overlap=1)
        result = chunker.chunk("0123456789")
        for chunk in result[:-1]:
            assert len(chunk) == 5

    def test_consecutive_chunks_overlap_correctly(self):
        """The tail of each chunk should match the head of the next by overlap chars."""
        overlap = 2
        chunker = SimpleChunker(chunk_size=5, overlap=overlap)
        # step=3: "abcdefghij" → ["abcde", "defgh", "ghij"]
        result = chunker.chunk("abcdefghij")
        assert len(result) >= 2
        for i in range(len(result) - 1):
            assert result[i][-overlap:] == result[i + 1][:overlap]

    def test_first_chunk_starts_at_beginning_of_text(self):
        """The first chunk should be the first chunk_size characters of the text."""
        chunker = SimpleChunker(chunk_size=5, overlap=2)
        text = "abcdefghijklmno"
        result = chunker.chunk(text)
        assert result[0] == text[:5]

    def test_last_chunk_contains_end_of_text(self):
        """The last chunk should include the final character of the text."""
        chunker = SimpleChunker(chunk_size=5, overlap=2)
        text = "abcdefghijklmno"
        result = chunker.chunk(text)
        assert result[-1][-1] == text[-1]
