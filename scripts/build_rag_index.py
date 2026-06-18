"""Build FAISS index from SRKI Dataset B responses, curriculum JSON, and optional web cache.

Produces `faiss.index` and `documents.json` in the configured `rag_index_dir`.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402
from backend.app.pipeline.web_scraper import load_cache, chunk_text  # noqa: E402


def load_dataset_b() -> list[dict]:
    with open(settings.srki_dataset_b, encoding="utf-8") as f:
        return json.load(f)


def load_json_curriculum() -> list[dict]:
    docs: list[dict] = []
    data_dir = settings.srki_json_data_dir
    if not data_dir or not data_dir.exists():
        return docs
    for path in data_dir.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except json.JSONDecodeError:
            continue
        text = json.dumps(payload, ensure_ascii=False)
        if len(text) < 80:
            continue
        docs.append(
            {
                "text": path.stem.replace("-", " "),
                "answer": f"# {path.stem}\n\n{text[:12000]}",
                "intent": "course_info",
                "source": str(path),
            }
        )
    return docs


def ingest_web_cache(pages: Iterable[dict]) -> list[dict]:
    docs: list[dict] = []
    for page in pages:
        url = page.get("url") or page.get("source") or ""
        title = page.get("title") or ""
        fetched_at = page.get("fetched_at")
        chunks = page.get("chunks") or chunk_text(page.get("text") or "")
        for i, chunk in enumerate(chunks):
            if not chunk or len(chunk) < 40:
                continue
            docs.append(
                {
                    "text": chunk,
                    "answer": chunk,
                    "intent": None,
                    "source": url,
                    "title": title,
                    "fetched_at": fetched_at,
                    "chunk_index": i,
                }
            )
    return docs


def build_index(documents: list[dict], embed_model: str = None) -> None:
    if not documents:
        raise RuntimeError("No documents to index.")
    model_name = embed_model or settings.embedding_model
    print(f"Encoding {len(documents)} documents with {model_name}...")
    encoder = SentenceTransformer(model_name)
    texts = [f"{d.get('text','')}\n{str(d.get('answer',''))[:500]}" for d in documents]
    embeddings = encoder.encode(texts, show_progress_bar=True, normalize_embeddings=True)
    embeddings = np.asarray(embeddings, dtype=np.float32)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    out = settings.rag_index_dir
    out.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(out / "faiss.index"))
    with open(out / "documents.json", "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)
    print(f"Saved index to {out}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build FAISS RAG index")
    parser.add_argument("--include-web", action="store_true", help="Include web cache pages in the index")
    parser.add_argument("--embed-model", type=str, default=None, help="Override embedding model")
    parser.add_argument("--max-docs", type=int, default=0, help="Limit number of documents indexed (0 = all)")
    args = parser.parse_args(argv or sys.argv[1:])

    documents: list[dict] = []
    seen: set[str] = set()

    for row in tqdm(load_dataset_b(), desc="Dataset B"):
        answer = (row.get("ideal_response") or "").strip()
        if not answer or len(answer) < 40:
            continue
        key = answer[:200]
        if key in seen:
            continue
        seen.add(key)
        documents.append(
            {
                "text": row.get("text", ""),
                "answer": answer,
                "intent": row.get("intent"),
                "context": row.get("context") or {},
                "dialogue_act": row.get("dialogue_act"),
                "source": "Dataset_B_SRKI",
            }
        )

    documents.extend(load_json_curriculum())

    if args.include_web:
        pages = load_cache()
        web_docs = ingest_web_cache(pages)
        # dedupe by snippet prefix
        for d in tqdm(web_docs, desc="Web pages"):
            key = d.get("text", "")[:200]
            if key in seen:
                continue
            seen.add(key)
            documents.append(d)

    if args.max_docs and args.max_docs > 0:
        documents = documents[: args.max_docs]

    build_index(documents, embed_model=args.embed_model)


if __name__ == "__main__":
    main()
