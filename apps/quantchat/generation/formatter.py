"""
Response Formatter
==================

Formats responses in structured, human-readable format.
"""

from typing import Dict, Any, List
from ..config.logging_config import setup_logger
from ..utils.tracing import traceable

logger = setup_logger("formatter")

class ResponseFormatter:
    """
    Formats responses with proper structure and citations.
    """
    
    @traceable(run_type="chain", name="ResponseFormatter.format_rag")
    def format_rag_response(
        self,
        response: str,
        sources: List[Dict[str, Any]],
        entity_names: List[str] = None,
        section: str = None
    ) -> str:
        """
        Format RAG response with sources.
        
        Args:
            response: Generated response
            sources: Source documents
            entity_names: Mentioned entities
            section: Requested section
        
        Returns:
            Formatted response string
        """
        formatted = response
        
        # Check if LLM already added inline sources - don't duplicate
        # LLM now adds sources at the end: **Source:** JD - [Title] or **Source:** Resume - [Name]
        has_inline_sources = "**Source:**" in response or "(Source:" in response or "Sources:" in response
        
        # Add sources section with deduplication (only if not already present)
        if sources and not has_inline_sources:
            seen_sources = set()
            unique_sources = []
            
            for source in sources:
                doc_type = source.get("doc_type", "Document").upper()
                entity = source.get("entity_name", "Unknown")
                source_key = f"{doc_type}:{entity}"
                
                if source_key not in seen_sources:
                    seen_sources.add(source_key)
                    unique_sources.append(f"  • {doc_type}: {entity}")
            
            if unique_sources:
                formatted += "\n\n---\nSources:\n"
                formatted += "\n".join(unique_sources) + "\n"
        
        return formatted
    
    def _format_structured_jd_full_doc(self, full_content: str, entity_name: str) -> str:
        """Format enterprise JD content that already uses `## Section` markdown."""
        formatted_lines = [
            f"# {entity_name}",
            "**JOB DESCRIPTION**",
            "",
            "---",
        ]

        for line in full_content.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("## "):
                formatted_lines.extend(["", stripped, ""])
                continue
            if stripped.startswith(("Job:", "Department:")):
                label, _, value = stripped.partition(":")
                formatted_lines.append(f"**{label.strip()}:** {value.strip()}")
                continue
            if stripped.startswith(("•", "-", "*", "●", "○", "►")):
                formatted_lines.append(f"- {stripped.lstrip('•-*●○► ')}")
                continue
            formatted_lines.append(stripped)

        formatted_lines.extend(["", "---", "*Complete document retrieved from database*"])
        return "\n".join(formatted_lines)

    @traceable(run_type="chain", name="ResponseFormatter.format_full_doc")
    def format_full_doc_response(
        self,
        full_content: str,
        document_type: str,
        entity_name: str
    ) -> str:
        """
        Format full document response with proper Markdown structure.
        
        Args:
            full_content: Complete document text
            document_type: "resume" or "jd"
            entity_name: Document entity name
        
        Returns:
            Formatted full document with Markdown
        """
        import re
        
        doc_type_label = "RESUME" if document_type == "resume" else "JOB DESCRIPTION"

        if document_type == "jd" and "## " in full_content:
            return self._format_structured_jd_full_doc(full_content.strip(), entity_name)
        
        # Section keywords to detect (sorted by length - longer first to avoid partial matches)
        section_keywords = [
            "PROFESSIONAL SUMMARY", "WORK EXPERIENCE", "KEY SKILLS", "TECHNICAL SKILLS",
            "CORE COMPETENCIES", "KEY RESPONSIBILITIES", "REQUIRED QUALIFICATIONS",
            "PREFERRED QUALIFICATIONS", "ABOUT THE COMPANY", "COMPANY OVERVIEW",
            "EMPLOYMENT HISTORY", "CAREER HISTORY", "ACADEMIC BACKGROUND",
            "PROFESSIONAL CERTIFICATIONS", "EDUCATION", "EXPERIENCE", "SKILLS",
            "PROJECTS", "CERTIFICATIONS", "ACHIEVEMENTS", "AWARDS", "SUMMARY",
            "PROFILE", "RESPONSIBILITIES", "REQUIREMENTS", "BENEFITS",
            "COMPENSATION", "LANGUAGES", "REFERENCES", "INTERESTS"
        ]
        # Sort by length (longer first) to match multi-word phrases before single words
        section_keywords = sorted(section_keywords, key=len, reverse=True)
        
        content = full_content.strip()
        
        # Use unique placeholders
        placeholder_id = 0
        replacements = {}
        
        # Simple approach: find section keywords that appear in UPPERCASE (common in resumes)
        # and insert newlines before them
        for keyword in section_keywords:
            # Only match if the keyword appears in uppercase (indicates a header)
            # This prevents matching "experience" in "years of experience"
            # Use case-sensitive match for the uppercase keyword
            pattern = rf'(?<!\S)({re.escape(keyword)})(?=\s|$|:|\n)'
            
            def make_replacement(match, kw=keyword):
                nonlocal placeholder_id
                matched_text = match.group(1)
                # Only treat as section if it's in uppercase (actual section header)
                if matched_text.isupper():
                    placeholder = f"<<<SEC{placeholder_id}>>>"
                    replacements[placeholder] = kw.title()
                    placeholder_id += 1
                    return f"\n\n{placeholder}\n"
                return matched_text
            
            # Case-sensitive regex to only match uppercase versions
            content = re.sub(pattern, make_replacement, content)
        
        # Build formatted output
        lines = content.split('\n')
        formatted_lines = []
        
        # Start with header
        formatted_lines.append(f"# {entity_name}")
        formatted_lines.append(f"**{doc_type_label}**")
        formatted_lines.append("")
        formatted_lines.append("---")
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Structured JD sections from pgvector reconstruction
            if stripped.startswith("## "):
                formatted_lines.append("")
                formatted_lines.append(stripped)
                formatted_lines.append("")
                continue

            bracket_header = re.match(r"^\[[^\]]+ - ([^\]]+)\]$", stripped)
            if bracket_header:
                formatted_lines.append("")
                formatted_lines.append(f"## {bracket_header.group(1).strip()}")
                formatted_lines.append("")
                continue
            
            # Check if this is a placeholder section header
            if stripped.startswith("<<<SEC") and stripped.endswith(">>>"):
                section_name = replacements.get(stripped, stripped)
                formatted_lines.append(f"\n## {section_name}\n")
                continue
            
            # Check for skill categories: "Category: Skill1, Skill2"
            if ':' in stripped and len(stripped.split(':')[0]) < 25 and not stripped.startswith('http'):
                parts = stripped.split(':', 1)
                formatted_lines.append(f"**{parts[0].strip()}:** {parts[1].strip()}")
            # Check if line looks like a bullet point
            elif stripped.startswith(('•', '-', '*', '●', '○', '►')):
                clean_bullet = stripped.lstrip('•-*●○► ')
                formatted_lines.append(f"- {clean_bullet}")
            else:
                formatted_lines.append(stripped)
        
        formatted_lines.append("")
        formatted_lines.append("---")
        formatted_lines.append("*Complete document retrieved from database*")
        
        return '\n'.join(formatted_lines)
    
    def format_general_response(self, response: str) -> str:
        """Format general knowledge response."""
        return response
    
    def format_comparison_response(
        self,
        response: str,
        entities: List[str],
        sources: List[Dict[str, Any]]
    ) -> str:
        """Format comparison response with deduplication."""
        formatted = response
        
        if entities:
            formatted += f"\n\n---\nComparing: {', '.join(entities)}"
        
        # Check if LLM already added inline sources - don't duplicate
        has_inline_sources = "(Source:" in response or "Sources:" in response
        
        if sources and not has_inline_sources:
            seen_sources = set()
            unique_sources = []
            
            for source in sources:
                doc_type = source.get("doc_type", "Document").upper()
                entity = source.get("entity_name", "Unknown")
                source_key = f"{doc_type}:{entity}"
                
                if source_key not in seen_sources:
                    seen_sources.add(source_key)
                    unique_sources.append(f"  • {doc_type}: {entity}")
            
            if unique_sources:
                formatted += "\n\nSources:\n" + "\n".join(unique_sources)
        
        return formatted
