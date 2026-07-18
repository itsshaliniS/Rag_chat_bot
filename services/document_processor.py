
import re
import uuid
import fitz  # PyMuPDF

import config


def extract_text(file_path, extension):
    print("extracting text from file:", file_path)
    if extension == "pdf":
        text = ""
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
        doc.close()
        return text

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def clean_text(text):
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # split paragraphs and clean
    paragraphs = text.split("\n\n")
    cleaned = []
    for p in paragraphs:
        cleaned.append(p.strip())
    text = "\n\n".join(cleaned)
    return text.strip()



def chunk_text(text, filename):
    paragraphs = [p for p in text.split("\n\n") if p.strip()]

    words = []
    for p in paragraphs:
        words.extend(p.split())
        words.append("\n\n")

    chunks = []
    start = 0
    chunk_number = 1

    while start < len(words):
        end = start + config.CHUNK_SIZE_WORDS
        chunk_words = words[start:end]
        chunk_str = " ".join(w for w in chunk_words if w != "\n\n").strip()

        if chunk_str:
            chunks.append({
                "id": str(uuid.uuid4()),
                "filename": filename,
                "chunk_number": chunk_number,
                "text": chunk_str,
            })
            chunk_number += 1

        if end >= len(words):
            break
        start = end - config.CHUNK_OVERLAP_WORDS

    print(f"chunking finished. Total chunks: {len(chunks)}")
    return chunks