"""
Knowledge Base module — Stage 3: RAG.
Handles PDF ingestion, chunking, embedding via sentence-transformers,
storage in ChromaDB, and retrieval of relevant chunks for grounded answers.
"""

import os
import logging
from pathlib import Path
from typing import Optional

from chromadb.types import Metadata
from typing import cast
from chromadb.api.types import EmbeddingFunction, Embeddable
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from PyPDF2 import PdfReader
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Where ChromaDB stores its data on disk
CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")

# Name of the single collection we use
COLLECTION_NAME = "support_knowledge_base"

# Chunking parameters
CHUNK_SIZE = 500       # characters per chunk
CHUNK_OVERLAP = 50     # overlap between consecutive chunks

# Retrieval defaults
DEFAULT_TOP_K = 3

# Embedding model — runs locally, no API cost
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_collection: Optional[Collection] = None
_client: Optional[ClientAPI] = None

def _get_embedding_function():
    """Return the SentenceTransformer embedding function."""
    return cast(
        EmbeddingFunction[Embeddable],
        SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    )


def _get_client() -> ClientAPI:
    """Lazy-init a persistent ChromaDB client."""
    global _client
    if _client is None:
        os.makedirs(CHROMA_DB_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        logger.info(f"ChromaDB client initialised at {CHROMA_DB_PATH}")
    return _client


def _get_collection() -> Collection:
    """Return (or create) the knowledge-base collection."""
    global _collection
    if _collection is None:
        client = _get_client()
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=_get_embedding_function(),
        )
        logger.info(
            f"Collection '{COLLECTION_NAME}' ready  "
            f"({collection.count()} documents)"
        )
        _collection = collection
    return _collection


# ---------------------------------------------------------------------------
# PDF → text extraction
# ---------------------------------------------------------------------------

def _extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """
    Read a PDF and return a list of dicts:
        [{"page": 1, "text": "..."}, ...]
    """
    reader = PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append({"page": i, "text": text})
    logger.info(f"Extracted text from {len(pages)} pages of {pdf_path}")
    return pages


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
                overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split *text* into chunks of approximately *chunk_size* characters,
    with *overlap* characters shared between consecutive chunks.
    """
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - overlap
    return chunks


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest_pdf(pdf_path: str, *, force: bool = False) -> int:
    """
    Read the PDF, chunk it, and upsert into ChromaDB.

    Returns the number of chunks stored.
    If the collection already has documents and *force* is False, skip.
    """
    collection = _get_collection()

    if collection.count() > 0 and not force:
        logger.info(
            f"Collection already has {collection.count()} docs — "
            "skipping ingestion (use force=True to rebuild)"
        )
        return collection.count()

    # If forcing, delete existing documents first
    if force and collection.count() > 0:
        logger.info("Force rebuild: deleting existing documents …")
        # Get all existing IDs and delete them
        existing = collection.get()
        if existing["ids"]:
            collection.delete(ids=existing["ids"])

    doc_name = Path(pdf_path).name
    pages = _extract_text_from_pdf(pdf_path)

    all_chunks: list[str] = []
    all_ids: list[str] = []
    all_metadatas: list[Metadata] = []

    chunk_counter = 0
    for page_info in pages:
        page_num = page_info["page"]
        page_text = page_info["text"]
        chunks = _chunk_text(page_text)

        for chunk_text in chunks:
            chunk_id = f"chunk_{chunk_counter:04d}"
            all_chunks.append(chunk_text)
            all_ids.append(chunk_id)
            all_metadatas.append({
                "doc_name": doc_name,
                "page_number": page_num,
                "chunk_id": chunk_id,
            })
            chunk_counter += 1

    if all_chunks:
        # ChromaDB has a batch size limit; upsert in batches of 500
        batch_size = 500
        for i in range(0, len(all_chunks), batch_size):
            collection.upsert(
                documents=all_chunks[i:i + batch_size],
                ids=all_ids[i:i + batch_size],
                metadatas=all_metadatas[i:i + batch_size],
            )

    logger.info(f"Ingested {chunk_counter} chunks from '{doc_name}'")
    return chunk_counter


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve_relevant_chunks(query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    collection = _get_collection()

    if collection.count() == 0:
        logger.warning("Knowledge base is empty — no chunks to retrieve")
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
    )

    chunks: list[dict] = []
    documents = results.get("documents")
    metadatas = results.get("metadatas")

    if documents and metadatas:
        for doc, meta in zip(documents[0], metadatas[0]):
            chunks.append({
                "chunk_id": meta["chunk_id"],
                "doc_name": meta["doc_name"],
                "page_number": meta["page_number"],
                "content": doc,
            })

    return chunks


# ---------------------------------------------------------------------------
# Convenience — initialise KB from the default PDF location
# ---------------------------------------------------------------------------

def initialise_knowledge_base(force: bool = False) -> int:
    """
    Find the default knowledge-base PDF and ingest it.
    Returns the number of chunks in the collection.
    """
    # Locate the PDF relative to the project root
    project_root = Path(__file__).resolve().parent.parent
    kb_dir = project_root / "knowledge base"

    pdf_files = list(kb_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDF files found in {kb_dir}")
        return 0

    total_chunks = 0
    for pdf_path in pdf_files:
        logger.info(f"Processing: {pdf_path.name}")
        total_chunks += ingest_pdf(str(pdf_path), force=force)

    return total_chunks
