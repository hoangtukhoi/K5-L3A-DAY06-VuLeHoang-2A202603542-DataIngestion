"""Store and search vectors using PostgreSQL + pgvector (exact cosine search, no ANN index)."""
from typing import Any

import psycopg

from .models import Chunk

ALLOWED_FILTERS = {"chapter": "chapter", "document_id": "document_id"}  # whitelist: column names are never user input


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in v) + "]"


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.database_url, self.dimensions = database_url, dimensions

    def _connect(self):
        return psycopg.connect(self.database_url, connect_timeout=5)

    def create_schema(self) -> None:
        """One table, rows keyed by (strategy, chunk_id). A vector dimension mismatch raises on insert."""
        with self._connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    strategy      text    NOT NULL,
                    chunk_id      text    NOT NULL,
                    document_id   text    NOT NULL,
                    source        text    NOT NULL,
                    page          integer NOT NULL,
                    chapter       integer,
                    chapter_title text,
                    text          text    NOT NULL,
                    embedding     vector({self.dimensions}) NOT NULL,
                    PRIMARY KEY (strategy, chunk_id)
                )""")
            conn.execute("CREATE INDEX IF NOT EXISTS chunks_filter_idx ON chunks (strategy, chapter)")

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> dict[str, int]:
        """Idempotent: same IDs are updated in place; rows of this strategy that are not in the
        incoming set (obsolete chunks of changed/removed documents) are deleted."""
        if len(chunks) != len(vectors):
            raise ValueError(f"{len(chunks)} chunks but {len(vectors)} vectors")
        if any(len(v) != self.dimensions for v in vectors):
            raise ValueError(f"vector dimension != {self.dimensions}")
        rows = [(strategy, c.chunk_id, c.document_id, c.source, c.page, c.metadata.get("chapter"),
                 c.metadata.get("chapter_title"), c.text, _vec(v)) for c, v in zip(chunks, vectors)]
        with self._connect() as conn:  # one transaction
            with conn.cursor() as cur:
                cur.executemany("""
                    INSERT INTO chunks (strategy, chunk_id, document_id, source, page, chapter, chapter_title, text, embedding)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)
                    ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                        document_id=EXCLUDED.document_id, source=EXCLUDED.source, page=EXCLUDED.page,
                        chapter=EXCLUDED.chapter, chapter_title=EXCLUDED.chapter_title,
                        text=EXCLUDED.text, embedding=EXCLUDED.embedding""", rows)
                cur.execute("DELETE FROM chunks WHERE strategy = %s AND NOT (chunk_id = ANY(%s))",
                            (strategy, [c.chunk_id for c in chunks]))
                removed = cur.rowcount
                cur.execute("SELECT count(*) FROM chunks WHERE strategy = %s", (strategy,))
                total = cur.fetchone()[0]
        return {"written": len(rows), "removed_obsolete": removed, "rows_in_db": total}

    def count(self, strategy: str) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT count(*) FROM chunks WHERE strategy = %s", (strategy,)).fetchone()[0]

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Metadata filters are applied in SQL; rank by cosine distance; score = cosine similarity."""
        if len(query_vector) != self.dimensions:
            raise ValueError("query vector dimension mismatch")
        where, params = ["strategy = %s"], [strategy]
        for key, value in (filters or {}).items():
            if key not in ALLOWED_FILTERS:
                raise ValueError(f"filter '{key}' not allowed; use one of {sorted(ALLOWED_FILTERS)}")
            where.append(f"{ALLOWED_FILTERS[key]} = %s"); params.append(value)
        qv = _vec(query_vector)
        sql = f"""SELECT chunk_id, text, 1 - (embedding <=> %s::vector) AS score,
                         document_id, source, page, chapter, chapter_title
                  FROM chunks WHERE {' AND '.join(where)}
                  ORDER BY embedding <=> %s::vector LIMIT %s"""
        with self._connect() as conn:
            rows = conn.execute(sql, [qv, *params, qv, top_k]).fetchall()
        return [{"chunk_id": r[0], "text": r[1], "score": float(r[2]),
                 "metadata": {"document_id": r[3], "source": r[4], "page": r[5],
                              "chapter": r[6], "chapter_title": r[7]}} for r in rows]
