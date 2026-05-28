"""
RAG Docs Query — Phase 4
Semantic search over indexed documentation (FO, SRD, MD, UTCD rows).
Two-stage pipeline: vector recall → rerank-2.5.

Called by prompt-evaluator to surface relevant requirements before implementation.

Run: python .claude/rag/docs_query.py "engine tick loop" --tool EXE
     python .claude/rag/docs_query.py "screener scoring logic" --tool SCR --final-k 5
     python .claude/rag/docs_query.py "position tracking" --artifact-type SRD
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Windows console may default to cp1252 — force UTF-8 for doc text output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import voyageai
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

DB_PATH = Path(__file__).parent / "qdrant_db"
COLLECTION = "docs"
EMBED_MODEL = "voyage-4-lite"
RERANK_MODEL = "rerank-2.5"
RECALL_K = 20
DEFAULT_FINAL_K = 8


# ── API key ───────────────────────────────────────────────────────────────────
def _api_key() -> str:
    key = os.environ.get("VOYAGE_API_KEY") or subprocess.check_output(
        ["powershell", "-Command",
         "[System.Environment]::GetEnvironmentVariable('VOYAGE_API_KEY','User')"],
        text=True,
    ).strip()
    if not key:
        print("[RAG] VOYAGE_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    return key


# ── Filter builder ────────────────────────────────────────────────────────────
def _build_filter(tool: str | None, artifact_type: str | None) -> Filter | None:
    conditions = []
    if tool:
        conditions.append(FieldCondition(key="tool", match=MatchValue(value=tool)))
    if artifact_type:
        conditions.append(FieldCondition(key="artifact_type", match=MatchValue(value=artifact_type)))
    return Filter(must=conditions) if conditions else None


# ── Main retrieval ────────────────────────────────────────────────────────────
def run(question: str, tool: str | None, artifact_type: str | None, final_k: int) -> None:
    if not DB_PATH.exists():
        print("[RAG] Qdrant DB not found — run ingest.py first", file=sys.stderr)
        sys.exit(1)

    qclient = QdrantClient(path=str(DB_PATH))
    existing = [c.name for c in qclient.get_collections().collections]
    if COLLECTION not in existing:
        print(f"[RAG] Collection '{COLLECTION}' not found — run docs_ingest.py first", file=sys.stderr)
        sys.exit(1)

    vc = voyageai.Client(api_key=_api_key())

    # Stage 1: Vector recall
    embed_result = vc.embed([question], model=EMBED_MODEL, input_type="query")
    hits = qclient.query_points(
        collection_name=COLLECTION,
        query=embed_result.embeddings[0],
        limit=RECALL_K,
        query_filter=_build_filter(tool, artifact_type),
    )
    candidates = [
        {**hit.payload, "vector_score": round(hit.score, 4)}
        for hit in hits.points
    ]

    if not candidates:
        print(f"[RAG] No results found for: '{question}'")
        return

    # Stage 2: Rerank
    rerank_result = vc.rerank(
        query=question,
        documents=[c["text"] for c in candidates],
        model=RERANK_MODEL,
        top_k=min(final_k, len(candidates)),
    )
    reranked = []
    for item in rerank_result.results:
        c = candidates[item.index].copy()
        c["rerank_score"] = round(item.relevance_score, 4)
        reranked.append(c)

    # Output formatted for Claude consumption
    filter_parts = []
    if tool:
        filter_parts.append(f"tool={tool}")
    if artifact_type:
        filter_parts.append(f"type={artifact_type}")
    filter_str = f"  filter: {', '.join(filter_parts)}" if filter_parts else ""

    print(f"\n=== RAG Docs Context ===")
    print(f"Query : '{question}'{filter_str}")
    print(f"Top {len(reranked)} of {len(candidates)} candidates\n")
    for i, c in enumerate(reranked, 1):
        print(
            f"[{i}] {c['tool']} | {c['artifact_type']}"
            f" | rerank={c['rerank_score']}  vector={c.get('vector_score', '?')}"
        )
        print(f"  ID  : {c['artifact_id']}")
        print(f"  Text: {c['text'][:350]}")
        print()
    print("=== End RAG Docs Context ===")


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Semantic search over indexed us_swing documentation."
    )
    parser.add_argument("query", nargs="+", help="Natural language query")
    parser.add_argument("--tool", help="Filter by tool code: EXE SCR GUI ANA INF MCP")
    parser.add_argument("--artifact-type", dest="artifact_type",
                        choices=["FO", "SRD", "MD", "UTCD", "RN", "ISS"],
                        help="Filter by artifact type")
    parser.add_argument("--final-k", dest="final_k", type=int, default=DEFAULT_FINAL_K,
                        help=f"Number of results to return (default {DEFAULT_FINAL_K})")
    args = parser.parse_args()

    run(
        question=" ".join(args.query),
        tool=args.tool,
        artifact_type=args.artifact_type,
        final_k=args.final_k,
    )


if __name__ == "__main__":
    main()
