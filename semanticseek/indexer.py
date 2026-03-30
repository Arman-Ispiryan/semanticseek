"""
indexer.py — File discovery and text chunking.
Supports .txt, .md, .pdf
"""

import re
from pathlib import Path
from typing import List, Dict

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}
CHUNK_SIZE = 400       # characters per chunk (roughly 80-100 tokens)
CHUNK_OVERLAP = 80     # overlap between chunks to preserve context


def discover_files(folder: Path) -> List[Path]:
    """Recursively find all supported files in a folder."""
    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(folder.rglob(f"*{ext}"))
    return sorted(files)


def extract_text(file: Path) -> str:
    """Extract raw text from a file based on its extension."""
    ext = file.suffix.lower()

    if ext in {".txt", ".md"}:
        try:
            return file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""

    elif ext == ".pdf":
        try:
            import fitz  # pymupdf
            doc = fitz.open(str(file))
            pages = []
            for page in doc:
                pages.append(page.get_text())
            doc.close()
            return "\n".join(pages)
        except Exception:
            return ""

    return ""


def clean_text(text: str) -> str:
    """Normalize whitespace and remove junk characters."""
    # Collapse excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse excessive spaces
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping chunks by word boundary.
    Tries to split on sentence/paragraph boundaries first.
    """
    if not text:
        return []

    # Split on paragraph boundaries first
    paragraphs = re.split(r"\n\n+", text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) < chunk_size:
            current = (current + " " + para).strip()
        else:
            if current:
                chunks.append(current)
            # If single paragraph is too large, split by sentence
            if len(para) > chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                sub = ""
                for sent in sentences:
                    if len(sub) + len(sent) < chunk_size:
                        sub = (sub + " " + sent).strip()
                    else:
                        if sub:
                            chunks.append(sub)
                        sub = sent
                if sub:
                    current = sub
                else:
                    current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    # Add overlap: prepend tail of previous chunk
    overlapped = []
    for i, chunk in enumerate(chunks):
        if i > 0 and overlap > 0:
            tail = chunks[i - 1][-overlap:]
            chunk = tail + " " + chunk
        overlapped.append(chunk.strip())

    return [c for c in overlapped if c]


def extract_chunks(file: Path) -> List[Dict]:
    """
    Full pipeline: extract text from file, clean it, chunk it.
    Returns list of dicts with text and metadata.
    """
    raw = extract_text(file)
    if not raw.strip():
        return []

    cleaned = clean_text(raw)
    chunks = chunk_text(cleaned)

    return [
        {
            "text": chunk,
            "file": str(file),
            "chunk_index": i,
            "file_name": file.name,
            "extension": file.suffix.lower(),
        }
        for i, chunk in enumerate(chunks)
    ]
