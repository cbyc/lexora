def chunk_text(body: str, chunk_size: int, overlap: int) -> list[str]:
    chunks = []

    step = chunk_size - overlap
    for i in range(0, len(body), step):
        chunk = body[i : i + chunk_size]
        chunks.append(chunk)

        # Stop if we've reached the end of the text
        if i + chunk_size >= len(body):
            break

    return chunks
