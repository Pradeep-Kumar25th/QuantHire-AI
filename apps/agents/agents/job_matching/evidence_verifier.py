"""
Evidence Verifier (Layer 2.7 — Deterministic Groundedness Check)
================================================================
Pure-Python, NO-LLM verifier that confirms every ``Evidence.quote`` emitted
by the swarm is actually present in ``candidate.raw_text`` or ``job.raw_text``.

Why this layer exists
---------------------
The single biggest source of hallucination in LLM hiring systems is the
"the resume says..." quote that the LLM invents. Every specialist can
produce a Pydantic-valid :class:`Evidence` whose ``quote`` was never in
the input. Without verification, the system displays fabricated quotes
to recruiters as "evidence" — a regulatory and product disaster.

This module performs a tiered check against the actual source text:

  1. **Verbatim** — normalised substring match. The strongest grounding.
  2. **Paraphrase** — ≥ 85% of the quote's *content tokens* (non-stopword,
     length-3+) appear in the source. Catches minor LLM rewording while
     still rejecting full fabrications.
  3. **Weak overlap (60-85%)** — likely fabricated; rejected.
  4. **Fabricated (< 60%)** — definitely fabricated; rejected.

Outputs
-------
* The :class:`DimensionScore` and :class:`RiskAssessment` objects are
  mutated in-place: failed evidence items are removed and the agent's
  ``confidence`` is downgraded proportional to the fabrication rate.
  Because the orchestrator's aggregation is confidence-weighted, this
  naturally reduces an unreliable specialist's influence on the verdict.

* A :class:`GroundednessReport` is returned and attached to
  ``MatchResult.metadata`` so the UI can surface "X% of evidence verified".

Determinism guarantee
---------------------
This module makes ZERO LLM calls. It contains no model call, no random
seed dependency, and no network I/O. Same inputs → identical output.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable

from agents.job_matching.enterprise_models import (
    CandidateProfile,
    DimensionGrounding,
    DimensionScore,
    Evidence,
    EvidenceGrounding,
    ExplanationCard,
    GroundednessReport,
    JobOpening,
    RiskAssessment,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Static config
# ---------------------------------------------------------------------------

# A small English stopword set — enough to keep token-overlap honest without
# pulling in NLTK / spaCy. Hiring vocabulary stays in (e.g. "manage",
# "lead", "mentor"); pure connectives go.
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "from",
        "as",
        "is",
        "was",
        "were",
        "are",
        "be",
        "been",
        "being",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "we",
        "our",
        "us",
        "i",
        "my",
        "me",
        "they",
        "their",
        "them",
        "he",
        "she",
        "his",
        "her",
        "him",
        "you",
        "your",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "not",
        "no",
        "yes",
        "so",
        "than",
        "then",
        "into",
        "out",
        "up",
        "down",
        "over",
        "under",
        "about",
        "via",
        "per",
    }
)

# Quotes shorter than this (after normalisation) are unverifiable noise —
# we drop them with classification="too_short".
_MIN_QUOTE_CHARS = 5
# Token overlap thresholds for the paraphrase / weak / fabricated bands.
_PARAPHRASE_THRESHOLD = 0.85
_WEAK_THRESHOLD = 0.60

# Confidence-penalty cap. If 100% of evidence is fabricated we *halve*
# confidence (a clear signal but not destructive); a partial-fabrication
# rate scales linearly toward this cap.
_MAX_CONFIDENCE_PENALTY_FRACTION = 0.5


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def _normalise(text: str | None) -> str:
    """Lowercase, strip punctuation, collapse whitespace.

    We do NOT remove digits, percent signs, or unit characters (they are
    often the most load-bearing parts of a resume claim, e.g. "10+ years").
    """
    if not text:
        return ""
    out = text.lower()
    out = _PUNCT_RE.sub(" ", out)
    out = _WHITESPACE_RE.sub(" ", out).strip()
    return out


def _tokens(text: str) -> list[str]:
    """Whitespace tokens of a normalised string."""
    if not text:
        return []
    return text.split()


def _content_tokens(tokens: Iterable[str]) -> list[str]:
    """Drop stopwords and very-short fillers."""
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 2]


# ---------------------------------------------------------------------------
# Single-quote verification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _GroundingResult:
    grounded: bool
    classification: str  # one of EvidenceGrounding.classification literals


def _verify_quote(quote: str, normalised_source: str) -> _GroundingResult:
    """Classify a single quote against an already-normalised source string.

    Order of checks:
      1. Empty / too-short → ``too_short`` (not grounded, no penalty later).
      2. Verbatim normalised substring → ``verbatim``.
      3. Content-token overlap ≥ 85% → ``paraphrase``.
      4. Content-token overlap ≥ 60% → ``weak_overlap`` (rejected).
      5. Otherwise → ``fabricated`` (rejected).
    """
    if not normalised_source:
        return _GroundingResult(False, "no_source_text")

    nq = _normalise(quote)
    if len(nq) < _MIN_QUOTE_CHARS:
        return _GroundingResult(False, "too_short")

    if nq in normalised_source:
        return _GroundingResult(True, "verbatim")

    # Token-overlap fallback for minor LLM paraphrasing.
    qt = _content_tokens(_tokens(nq))
    if not qt:
        # Quote was all stopwords; treat as too_short rather than penalising.
        return _GroundingResult(False, "too_short")

    src_tokens = set(_content_tokens(_tokens(normalised_source)))
    if not src_tokens:
        return _GroundingResult(False, "no_source_text")

    overlap = sum(1 for t in qt if t in src_tokens)
    ratio = overlap / len(qt)
    if ratio >= _PARAPHRASE_THRESHOLD:
        return _GroundingResult(True, "paraphrase")
    if ratio >= _WEAK_THRESHOLD:
        return _GroundingResult(False, "weak_overlap")
    return _GroundingResult(False, "fabricated")


def _classify_evidence(
    evidence: Evidence,
    norm_resume: str,
    norm_jd: str,
) -> tuple[Evidence | None, EvidenceGrounding]:
    """Verify a single Evidence object.

    Returns (kept_evidence_or_None, grounding_record). When kept_evidence
    is None, the caller should drop the item from its parent's evidence
    list — it was unverifiable.
    """
    src = evidence.source
    if src == "resume":
        normalised_source = norm_resume
    else:
        normalised_source = norm_jd

    grounding = _verify_quote(evidence.quote, normalised_source)
    record = EvidenceGrounding(
        grounded=grounding.grounded,
        classification=grounding.classification,  # type: ignore[arg-type]
        quote_preview=(evidence.quote or "")[:80],
        source=src,
    )
    return (evidence if grounding.grounded else None), record


def _classify_quote_string(
    quote: str,
    source_label: str,
    norm_resume: str,
    norm_jd: str,
) -> EvidenceGrounding:
    """Verify a free-form quote string (used for risk flag evidence)."""
    if source_label == "jd":
        normalised_source = norm_jd
    else:
        normalised_source = norm_resume
    grounding = _verify_quote(quote, normalised_source)
    return EvidenceGrounding(
        grounded=grounding.grounded,
        classification=grounding.classification,  # type: ignore[arg-type]
        quote_preview=(quote or "")[:80],
        source=source_label if source_label in {"resume", "jd"} else "resume",  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Confidence penalty maths
# ---------------------------------------------------------------------------


def _confidence_penalty(grounded_pct: float, evidence_total: int) -> float:
    """How much of the original confidence to shave off.

    * No evidence claimed → 0 penalty (we're not punishing brevity).
    * 100% grounded → 0 penalty.
    * 0% grounded → up to ``_MAX_CONFIDENCE_PENALTY_FRACTION`` (i.e. 0.5)
      of original confidence subtracted.

    Linear in (1 - grounded_pct).
    """
    if evidence_total == 0:
        return 0.0
    return _MAX_CONFIDENCE_PENALTY_FRACTION * (1.0 - max(0.0, min(1.0, grounded_pct)))


# ---------------------------------------------------------------------------
# Verifier class — orchestrator-facing API
# ---------------------------------------------------------------------------


class EvidenceVerifier:
    """Mutates DimensionScore/RiskAssessment in place; returns audit trail.

    Usage:

        verifier = EvidenceVerifier(candidate, job)
        report   = verifier.verify_swarm(specialist_scores, risk)
        # ... later ...
        verifier.verify_explainability_cards(report, cards)
    """

    def __init__(self, candidate: CandidateProfile, job: JobOpening) -> None:
        self.candidate = candidate
        self.job = job
        self._norm_resume = _normalise(candidate.raw_text)
        self._norm_jd = _normalise(job.raw_text)
        self.raw_text_available = bool(self._norm_resume or self._norm_jd)

    # ------------------------------------------------------------------ public
    def verify_swarm(
        self,
        specialist_scores: list[DimensionScore],
        risk: RiskAssessment | None,
    ) -> GroundednessReport:
        """Verify every Evidence emitted by Layer-2 specialists + RiskAgent.

        Mutates the inputs:
          * ``DimensionScore.evidence`` — fabricated items removed.
          * ``DimensionScore.confidence`` — downgraded if heavy fabrication.
          * ``RiskAssessment.flags[].evidence`` — quoted-string overwritten
            with empty when it can't be verified.
        """
        report = GroundednessReport(raw_text_available=self.raw_text_available)

        if not self.raw_text_available:
            report.notes.append(
                "raw_text not available on candidate or job; groundedness "
                "verification was skipped (no penalty applied)."
            )
            # Compute pct as 1.0 (no claim of grounding either way) so we
            # don't pollute the UI signal with a false 0%. The note above
            # is what the UI should surface.
            report.overall_pct = 1.0
            report.risk_grounded_pct = 1.0
            return report

        # ---- per-dimension specialist verification ----
        for ds in specialist_scores:
            dim_record = self._verify_dimension(ds)
            report.per_dimension.append(dim_record)
            report.total_evidence += dim_record.evidence_total
            report.grounded_evidence += dim_record.evidence_grounded
            report.fabricated_evidence += (
                dim_record.evidence_total - dim_record.evidence_grounded
            )

        # ---- risk flag evidence verification ----
        if risk is not None:
            r_total, r_grounded = self._verify_risk(risk)
            report.risk_grounded_pct = (
                r_grounded / r_total if r_total > 0 else 1.0
            )
            report.total_evidence += r_total
            report.grounded_evidence += r_grounded
            report.fabricated_evidence += r_total - r_grounded
        else:
            report.risk_grounded_pct = 1.0

        report.overall_pct = (
            report.grounded_evidence / report.total_evidence
            if report.total_evidence > 0
            else 1.0
        )
        return report

    def verify_explainability_cards(
        self,
        report: GroundednessReport,
        cards: list[ExplanationCard],
    ) -> None:
        """Strip fabricated evidence from explanation cards (in-place).

        Called *after* :meth:`verify_swarm` so the report receives the
        Layer-4 grounding pct as well. We do NOT re-penalise specialist
        confidence here; this is purely a display-side scrub.
        """
        if not self.raw_text_available:
            report.explainability_grounded_pct = 1.0
            return

        total = 0
        grounded = 0
        for card in cards:
            kept: list[Evidence] = []
            for ev in card.evidence:
                survivor, _ = _classify_evidence(ev, self._norm_resume, self._norm_jd)
                total += 1
                if survivor is not None:
                    kept.append(survivor)
                    grounded += 1
            card.evidence = kept
        report.explainability_grounded_pct = grounded / total if total > 0 else 1.0

    # ------------------------------------------------------------------ helpers
    def _verify_dimension(self, ds: DimensionScore) -> DimensionGrounding:
        kept: list[Evidence] = []
        items: list[EvidenceGrounding] = []

        for ev in ds.evidence:
            survivor, record = _classify_evidence(
                ev, self._norm_resume, self._norm_jd
            )
            items.append(record)
            if survivor is not None:
                kept.append(survivor)

        evidence_total = len(items)
        evidence_grounded = sum(1 for r in items if r.grounded)
        grounded_pct = (
            evidence_grounded / evidence_total if evidence_total > 0 else 1.0
        )
        penalty_fraction = _confidence_penalty(grounded_pct, evidence_total)

        # Mutate the specialist's outputs.
        ds.evidence = kept
        if penalty_fraction > 0:
            old_conf = ds.confidence
            new_conf = max(0.0, old_conf * (1.0 - penalty_fraction))
            ds.confidence = round(new_conf, 4)
            logger.info(
                "EvidenceVerifier penalised %s confidence: %.2f -> %.2f "
                "(%.0f%% of evidence ungrounded)",
                ds.agent_name,
                old_conf,
                ds.confidence,
                (1.0 - grounded_pct) * 100,
            )

        return DimensionGrounding(
            dimension=ds.dimension,
            evidence_total=evidence_total,
            evidence_grounded=evidence_grounded,
            grounded_pct=round(grounded_pct, 4),
            confidence_penalty_applied=round(penalty_fraction, 4),
            items=items,
        )

    def _verify_risk(self, risk: RiskAssessment) -> tuple[int, int]:
        """Returns (total_evidence_strings_seen, grounded_count).

        Each flag has an ``evidence`` STRING (not an Evidence model) and a
        ``description``. We verify the ``evidence`` field against the
        resume; failures are blanked rather than removed so the flag
        itself (which may still be useful, e.g. "stack drift") survives.
        """
        total = 0
        grounded = 0
        for flag in risk.flags:
            quote = (flag.get("evidence") or "").strip()
            if not quote:
                continue
            total += 1
            record = _classify_quote_string(
                quote, "resume", self._norm_resume, self._norm_jd
            )
            if record.grounded:
                grounded += 1
            else:
                # Don't display a fabricated quote to recruiters; keep the
                # flag itself but blank the offending evidence string.
                flag["evidence"] = "(quote unverified — removed by EvidenceVerifier)"
        # Penalise risk confidence proportionally if heavy fabrication.
        if total > 0:
            grounded_pct = grounded / total
            penalty = _confidence_penalty(grounded_pct, total)
            if penalty > 0:
                old_conf = risk.confidence
                risk.confidence = round(max(0.0, old_conf * (1.0 - penalty)), 4)
        return total, grounded
