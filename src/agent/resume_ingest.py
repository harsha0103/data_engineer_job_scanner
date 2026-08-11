"""One-off ingestion of the base resume — extract text, embed, store.

Run this again whenever the resume file changes; Streamlit reads whatever's
in embedd.base_resume rather than re-parsing/re-embedding on every page load.
"""

import docx

from embedding.openai_embeddings import embed_text
from storage.resume import set_base_resume


def ingest_base_resume(file_path: str) -> None:
    doc = docx.Document(file_path)
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    embedding = embed_text(text)
    set_base_resume(file_path, text, embedding)
