"""Write resume/JD chunks to Postgres pgvector (Azure Non-Prod RAG path)."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_chunks import DocumentChunk

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
_MAX_FULL_CONTENT = 65535
_JD_DOCUMENT_TYPES = ("job_description", "jd")


def _format_pgvector_literal(values: List[float]) -> str:
    """Format embedding for raw SQL pgvector distance queries."""
    return "[" + ",".join(str(float(value)) for value in values) + "]"


def _ensure_quantchat_path() -> None:
    apps_root = Path(__file__).resolve().parents[3]
    if str(apps_root) not in sys.path:
        sys.path.insert(0, str(apps_root))


def _ensure_agents_path() -> None:
    agents_root = Path(__file__).resolve().parents[3] / "agents"
    agents_parent = agents_root.parent
    if agents_root.is_dir() and str(agents_parent) not in sys.path:
        sys.path.insert(0, str(agents_parent))


def _embedding_model_label() -> str:
    _ensure_agents_path()
    from agents.rag.unified_embeddings import embedding_model_label

    return embedding_model_label()


def _encode_texts(texts: List[str]) -> List[List[float]]:
    _ensure_agents_path()
    from agents.rag.unified_embeddings import encode_texts

    return encode_texts(texts)


def _chunk_resume(parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    _ensure_quantchat_path()
    from quantchat.ingestion.chunking import ResumeChunker

    return ResumeChunker().chunk_resume(parsed_data)


def _chunk_jd(jd_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    _ensure_quantchat_path()
    from quantchat.ingestion.chunking import JDChunker

    return JDChunker().chunk_jd(jd_data)


def _structured_full_content(parsed_data: Dict[str, Any], chunks: List[Dict[str, Any]]) -> str:
    parts = []
    name = parsed_data.get("personal_info", {}).get("name", "Unknown")
    parts.append(f"Candidate: {name}")
    for chunk in chunks:
        section = chunk.get("section") or "Section"
        content = chunk.get("content") or ""
        parts.append(f"\n## {section}\n{content}")
    full = "\n".join(parts).strip()
    return full[:_MAX_FULL_CONTENT]


def _structured_jd_full_content(jd_data: Dict[str, Any], chunks: List[Dict[str, Any]]) -> str:
    _ensure_quantchat_path()
    from quantchat.ingestion.chunking import (
        format_jd_department_team,
        format_jd_job_title_block,
        jd_removed_section_ids,
    )

    parts = []
    removed = jd_removed_section_ids(jd_data)
    title = format_jd_job_title_block(jd_data) or jd_data.get("job_title") or jd_data.get("title") or "Job Description"
    if "job_title" not in removed:
        parts.append(f"Job: {title}")
    dept = format_jd_department_team(jd_data)
    if dept and "department_team" not in removed:
        parts.append(f"Department: {dept}")
    for chunk in chunks:
        section = chunk.get("section") or "Section"
        content = chunk.get("content") or ""
        parts.append(f"\n## {section}\n{content}")
    full = "\n".join(parts).strip()
    return full[:_MAX_FULL_CONTENT]


def _document_type_clause(document_type: Optional[str]) -> tuple[str, Dict[str, Any]]:
    if not document_type:
        return "", {}
    if document_type == "jd":
        return "document_type IN ('job_description', 'jd')", {}
    return "document_type = :document_type", {"document_type": document_type}


def _entity_filter_clause(
    *,
    entity_name: Optional[str] = None,
    entity_names: Optional[List[str]] = None,
) -> tuple[List[str], Dict[str, Any]]:
    names: List[str] = []
    for raw in entity_names or []:
        cleaned = str(raw or "").strip()
        if cleaned and cleaned not in names:
            names.append(cleaned)
    if entity_name:
        cleaned = str(entity_name).strip()
        if cleaned and cleaned not in names:
            names.append(cleaned)
    if not names:
        return [], {}

    if len(names) == 1:
        return ["entity_name ILIKE :entity_name_0"], {"entity_name_0": f"%{names[0]}%"}

    parts: List[str] = []
    params: Dict[str, Any] = {}
    for idx, name in enumerate(names[:5]):
        key = f"entity_name_{idx}"
        parts.append(f"entity_name ILIKE :{key}")
        params[key] = f"%{name}%"
    return ["(" + " OR ".join(parts) + ")"], params


def _section_filter_clause(section_type: Optional[str]) -> tuple[str, Dict[str, Any]]:
    if not section_type:
        return "", {}
    return "section_type ILIKE :section_type", {"section_type": f"%{section_type}%"}


def _quantchat_visibility_clauses() -> List[str]:
    """Exclude deleted jobs and removed (inactive) candidates from QuantChat retrieval.

    Belt-and-suspenders alongside ResourceDeletionService chunk purge: even if a
    chunk row survives delete, it will not be returned by search or full-doc fetch.
    """
    return [
        "(candidate_id IS NULL OR candidate_id IN "
        "(SELECT id FROM candidates WHERE is_active = true))",
        "(job_id IS NULL OR job_id IN (SELECT id FROM jobs))",
    ]


def _apply_common_filters(
    clauses: List[str],
    params: Dict[str, Any],
    *,
    document_type: Optional[str] = None,
    entity_name: Optional[str] = None,
    entity_names: Optional[List[str]] = None,
    document_id: Optional[str] = None,
    section_type: Optional[str] = None,
    apply_visibility: bool = True,
) -> None:
    if document_type:
        type_clause, type_params = _document_type_clause(document_type)
        clauses.append(type_clause)
        params.update(type_params)
    entity_clauses, entity_params = _entity_filter_clause(
        entity_name=entity_name,
        entity_names=entity_names,
    )
    clauses.extend(entity_clauses)
    params.update(entity_params)
    if document_id:
        clauses.append("document_id = :document_id")
        params["document_id"] = document_id
    section_clause, section_params = _section_filter_clause(section_type)
    if section_clause:
        clauses.append(section_clause)
        params.update(section_params)
    if apply_visibility:
        clauses.extend(_quantchat_visibility_clauses())


_SECTION_ORDER = [
    "Personal Info",
    "Summary",
    "Skills",
    "Experience",
    "Education",
    "Projects",
    "Certifications",
    "Job Title",
    "Department",
    "Location",
    "About Company",
    "Position Summary",
    "Responsibilities",
    "Required Qualifications",
    "Preferred Qualifications",
    "Soft Skills",
    "Tools & Technologies",
    "Success Metrics",
    "Work Environment",
    "Compensation & Benefits",
    "Equal Opportunity",
    "Application Instructions",
]


CUSTOM_JD_SECTION_PREFIX = "Custom: "


def _jd_section_display_name(section: str) -> str:
    if section.startswith(CUSTOM_JD_SECTION_PREFIX):
        return section[len(CUSTOM_JD_SECTION_PREFIX):].strip()
    return section


def _strip_jd_chunk_context_prefix(chunk_text: str) -> str:
    """Remove `[Job Title - Section]` prefix from indexed JD chunk text."""
    text = (chunk_text or "").strip()
    if not text:
        return ""
    if text.startswith("[") and "]\n" in text:
        return text.split("]\n", 1)[1].strip()
    if text.startswith("[") and "]" in text:
        return text.split("]", 1)[1].lstrip("\n").strip()
    return text


def _normalize_jd_section_body(section: str, body: str) -> str:
    """Drop redundant `Section:` prefix when it matches the section header."""
    text = (body or "").strip()
    if not text or not section:
        return text
    prefix = f"{section}:"
    if text.lower().startswith(prefix.lower()):
        return text[len(prefix):].lstrip()
    return text


def _reconstruct_jd_full_content(rows: list) -> str:
    """Build structured markdown for QuantChat from pgvector JD chunk rows."""
    indexed_rows = list(enumerate(rows))
    indexed_rows.sort(key=lambda item: (_section_sort_key(item[1][3] or ""), item[0]))
    parts: list[str] = []
    for _, row in indexed_rows:
        section = (row[3] or "Section").strip()
        display_section = _jd_section_display_name(section)
        body = _normalize_jd_section_body(
            display_section,
            _strip_jd_chunk_context_prefix(row[4] or ""),
        )
        if not section and not body:
            continue
        parts.append(
            f"## {display_section}\n{body}" if body else f"## {display_section}"
        )
    return "\n\n".join(parts).strip()


def _section_sort_key(section: str) -> int:
    if section.startswith(CUSTOM_JD_SECTION_PREFIX):
        return len(_SECTION_ORDER) + 1
    try:
        return _SECTION_ORDER.index(section)
    except ValueError:
        return len(_SECTION_ORDER)

class PgVectorIngestionService:
    """Chunk, embed, and persist documents for QuantChat retrieval on pgvector."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def delete_document(self, document_id: str) -> int:
        result = await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        await self.session.flush()
        return result.rowcount or 0

    async def add_resume(
        self,
        parsed_data: Dict[str, Any],
        *,
        candidate_id: Optional[UUID] = None,
    ) -> str:
        resume_id = parsed_data.get("id") or str(candidate_id)
        if not resume_id:
            raise ValueError("resume document id is required")

        candidate_name = parsed_data.get("personal_info", {}).get("name", "Unknown")
        candidate_email = parsed_data.get("personal_info", {}).get("email", "")

        await self._dedupe_by_candidate(candidate_name, candidate_email)
        await self.delete_document(str(resume_id))

        chunks = _chunk_resume(parsed_data)
        if not chunks:
            raise ValueError("No chunks created from resume")

        chunk_texts = [chunk["content"] for chunk in chunks]
        embeddings = await asyncio.to_thread(_encode_texts, chunk_texts)
        full_content = _structured_full_content(parsed_data, chunks)
        model_label = _embedding_model_label()

        full_content_stored = False
        for chunk, embedding in zip(chunks, embeddings):
            chunk_full = full_content if not full_content_stored else None
            if not full_content_stored:
                full_content_stored = True

            row = DocumentChunk(
                document_id=str(chunk.get("entity_id") or resume_id),
                document_type="resume",
                entity_name=chunk.get("entity_name") or candidate_name,
                section_type=chunk.get("section") or "",
                chunk_text=chunk.get("content") or "",
                full_content=chunk_full,
                candidate_id=candidate_id,
                vector=embedding,
                embedding_model=model_label,
            )
            self.session.add(row)

        await self.session.flush()
        logger.info(
            "Resume %s stored in pgvector (%s chunks, candidate_id=%s)",
            resume_id,
            len(chunks),
            candidate_id,
        )
        return str(resume_id)

    async def add_jd(
        self,
        jd_data: Dict[str, Any],
        *,
        job_id: Optional[UUID] = None,
    ) -> str:
        document_id = jd_data.get("id")
        if not document_id:
            raise ValueError("JD document id is required")

        job_title = jd_data.get("job_title") or jd_data.get("title") or "Untitled Role"
        department = jd_data.get("department") or ""

        await self._purge_jd_chunks(
            str(document_id),
            job_title,
            job_id=job_id,
        )

        chunks = _chunk_jd(jd_data)
        if not chunks:
            raise ValueError("No chunks created from job description")

        chunk_texts = [chunk["content"] for chunk in chunks]
        embeddings = await asyncio.to_thread(_encode_texts, chunk_texts)
        full_content = _structured_jd_full_content(jd_data, chunks)
        model_label = _embedding_model_label()

        full_content_stored = False
        for chunk, embedding in zip(chunks, embeddings):
            chunk_full = full_content if not full_content_stored else None
            if not full_content_stored:
                full_content_stored = True

            row = DocumentChunk(
                document_id=str(chunk.get("entity_id") or document_id),
                document_type="job_description",
                entity_name=chunk.get("entity_name") or job_title,
                section_type=chunk.get("section") or "",
                chunk_text=chunk.get("content") or "",
                full_content=chunk_full,
                job_id=job_id,
                vector=embedding,
                embedding_model=model_label,
            )
            self.session.add(row)

        await self.session.flush()
        logger.info(
            "JD %s stored in pgvector (%s chunks, job_id=%s)",
            document_id,
            len(chunks),
            job_id,
        )
        return str(document_id)

    async def _dedupe_by_candidate(self, name: str, email: str) -> None:
        cleaned_name = name
        try:
            _ensure_quantchat_path()
            from quantchat.ingestion.chunking import _clean_entity_name

            cleaned_name = _clean_entity_name(name)
        except Exception:
            pass

        if cleaned_name and cleaned_name != "Unknown":
            await self.session.execute(
                text(
                    "DELETE FROM document_chunks "
                    "WHERE document_type = 'resume' "
                    "AND (entity_name = :name OR entity_name = :cleaned_name)"
                ),
                {"name": name, "cleaned_name": cleaned_name},
            )
        if email:
            await self.session.execute(
                text(
                    """
                    DELETE FROM document_chunks
                    WHERE candidate_id IN (SELECT id FROM candidates WHERE email = :email)
                    """
                ),
                {"email": email},
            )

    async def _purge_jd_chunks(
        self,
        document_id: str,
        job_title: str,
        *,
        job_id: Optional[UUID] = None,
    ) -> None:
        """Remove all prior JD vectors for this document/job before re-indexing."""
        await self.delete_document(str(document_id))
        if job_id:
            await self.session.execute(
                text("DELETE FROM document_chunks WHERE job_id = :job_id"),
                {"job_id": str(job_id)},
            )
        if job_title:
            await self.session.execute(
                text(
                    """
                    DELETE FROM document_chunks
                    WHERE document_type IN ('job_description', 'jd')
                      AND entity_name = :title
                      AND document_id <> :document_id
                    """
                ),
                {"title": job_title, "document_id": str(document_id)},
            )
        await self._dedupe_jd(document_id, job_title, department="")

    async def _dedupe_jd(self, document_id: str, job_title: str, department: str) -> None:
        await self.session.execute(
            text("DELETE FROM document_chunks WHERE document_id = :document_id"),
            {"document_id": document_id},
        )
        if job_title and department:
            await self.session.execute(
                text(
                    """
                    DELETE FROM document_chunks
                    WHERE document_type IN ('job_description', 'jd')
                      AND entity_name = :title
                      AND section_type = 'Department'
                      AND chunk_text ILIKE :dept_pattern
                    """
                ),
                {"title": job_title, "dept_pattern": f"%{department[:80]}%"},
            )

    async def search_chunks(
        self,
        query_embedding: List[float],
        *,
        document_type: Optional[str] = None,
        entity_name: Optional[str] = None,
        entity_names: Optional[List[str]] = None,
        document_id: Optional[str] = None,
        section_type: Optional[str] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        clauses = ["vector IS NOT NULL"]
        params: Dict[str, Any] = {
            "query_vector": _format_pgvector_literal(query_embedding),
            "limit": top_k,
        }
        _apply_common_filters(
            clauses,
            params,
            document_type=document_type,
            entity_name=entity_name,
            entity_names=entity_names,
            document_id=document_id,
            section_type=section_type,
        )

        where_sql = " AND ".join(clauses)
        sql = f"""
            SELECT document_id, document_type, entity_name, section_type,
                   chunk_text, full_content, created_at,
                   1 - (vector <=> CAST(:query_vector AS vector)) AS score
            FROM document_chunks
            WHERE {where_sql}
            ORDER BY vector <=> CAST(:query_vector AS vector)
            LIMIT :limit
        """
        result = await self.session.execute(text(sql), params)
        rows = result.fetchall()
        return [
            {
                "document_id": row[0],
                "document_type": row[1],
                "entity_name": row[2],
                "section_type": row[3],
                "chunk_text": row[4],
                "full_content": row[5] or "",
                "created_at": row[6],
                "score": float(row[7] or 0.0),
            }
            for row in rows
        ]

    async def search_chunks_by_keywords(
        self,
        keywords: List[str],
        *,
        document_type: Optional[str] = None,
        entity_name: Optional[str] = None,
        entity_names: Optional[List[str]] = None,
        document_id: Optional[str] = None,
        section_type: Optional[str] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        if not keywords and not entity_name and not entity_names and not document_id:
            return []

        clauses: List[str] = ["1=1"]
        params: Dict[str, Any] = {"limit": top_k}

        _apply_common_filters(
            clauses,
            params,
            document_type=document_type,
            entity_name=entity_name,
            entity_names=entity_names,
            document_id=document_id,
            section_type=section_type,
        )

        keyword_clauses = []
        for idx, keyword in enumerate(keywords[:8]):
            key = f"kw_{idx}"
            keyword_clauses.append(f"chunk_text ILIKE :{key}")
            params[key] = f"%{keyword}%"
        if keyword_clauses:
            clauses.append("(" + " OR ".join(keyword_clauses) + ")")

        where_sql = " AND ".join(clauses)
        sql = f"""
            SELECT document_id, document_type, entity_name, section_type,
                   chunk_text, full_content, created_at
            FROM document_chunks
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT :limit
        """
        result = await self.session.execute(text(sql), params)
        rows = result.fetchall()
        return [
            {
                "document_id": row[0],
                "document_type": row[1],
                "entity_name": row[2],
                "section_type": row[3],
                "chunk_text": row[4],
                "full_content": row[5] or "",
                "created_at": row[6],
                "score": 1.0,
            }
            for row in rows
        ]

    async def fetch_full_document(
        self,
        *,
        document_type: str,
        entity_name: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        from quantchat.retrieval.entity_match import name_match_score

        _ensure_quantchat_path()

        type_clause, type_params = _document_type_clause(document_type)
        resolved_document_id = document_id

        if not resolved_document_id and entity_name:
            entity_clauses, entity_params = _entity_filter_clause(entity_name=entity_name)
            search_clauses = [type_clause] + entity_clauses + _quantchat_visibility_clauses()
            search_params = dict(type_params)
            search_params.update(entity_params)
            candidate_sql = f"""
                SELECT document_id, entity_name, MAX(created_at) AS latest_at
                FROM document_chunks
                WHERE {" AND ".join(search_clauses)}
                GROUP BY document_id, entity_name
                LIMIT 200
            """
            candidate_result = await self.session.execute(
                text(candidate_sql), search_params
            )
            candidates = candidate_result.fetchall()
            if candidates:
                best_row = None
                best_score = -1.0
                for row in candidates:
                    score = name_match_score(entity_name, row[1] or "")
                    if score <= 0:
                        continue
                    latest_at = row[2]
                    if (
                        best_row is None
                        or score > best_score
                        or (score == best_score and latest_at and latest_at > best_row[2])
                    ):
                        best_score = score
                        best_row = row
                if best_row is not None:
                    resolved_document_id = best_row[0]
                elif len(candidates) == 1:
                    resolved_document_id = candidates[0][0]

        if not resolved_document_id:
            return None

        fetch_clauses = [type_clause, "document_id = :document_id"] + _quantchat_visibility_clauses()
        fetch_params = dict(type_params)
        fetch_params["document_id"] = resolved_document_id
        fetch_params["limit"] = 1000

        sql = f"""
            SELECT document_id, document_type, entity_name, section_type,
                   chunk_text, full_content, created_at
            FROM document_chunks
            WHERE {" AND ".join(fetch_clauses)}
            ORDER BY created_at ASC
            LIMIT :limit
        """
        result = await self.session.execute(text(sql), fetch_params)
        rows = result.fetchall()
        if not rows:
            return None

        rows_sorted = sorted(
            enumerate(rows),
            key=lambda item: (_section_sort_key(item[1][3] or ""), item[0]),
        )
        ordered_rows = [row for _, row in rows_sorted]
        hit = ordered_rows[0]
        full_content = _reconstruct_jd_full_content(ordered_rows)
        if not full_content:
            full_content = next((row[5] for row in ordered_rows if row[5]), "") or ""
        if not full_content:
            full_content = "\n\n".join(row[4] or "" for row in ordered_rows if row[4])

        return {
            "document_id": hit[0],
            "document_type": hit[1],
            "entity_name": hit[2],
            "full_content": full_content,
            "section_type": "Complete Document",
        }
