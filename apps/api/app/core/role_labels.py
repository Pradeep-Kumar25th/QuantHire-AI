"""Canonical RBAC role spellings per layer (Entra, PostgreSQL, JWT, UI).

Hazim / Azure Non-Prod reference (xx1@malomatia.com):
  Entra app role  → RECRUITER
  PostgreSQL enum → RECRUITER
  JWT / Python    → recruiter
  UI header label → RECRUITER

All 8 HR recruiters must use the same RECRUITER chain as xx1.
"""

from __future__ import annotations

# Entra ID token ``roles`` claim (app role *value* after normalization).
ENTRA_ROLE_ADMIN = "ADMIN"
ENTRA_ROLE_RECRUITER = "RECRUITER"
ENTRA_ROLE_HIRING_MANAGER = "HIRING_MANAGER"
ENTRA_ROLE_INTERVIEWER = "INTERVIEWER"
ENTRA_ROLE_VIEWER = "VIEWER"

# PostgreSQL ``userrole`` enum labels on Azure Non-Prod (viewer is lowercase exception).
PG_ENUM_ADMIN = "ADMIN"
PG_ENUM_RECRUITER = "RECRUITER"
PG_ENUM_HIRING_MANAGER = "HIRING_MANAGER"
PG_ENUM_INTERVIEWER = "INTERVIEWER"
PG_ENUM_VIEWER = "viewer"
PG_ENUM_CANDIDATE = "CANDIDATE"

# JWT claim + Python UserRole.value (always lowercase snake_case).
JWT_ROLE_ADMIN = "admin"
JWT_ROLE_RECRUITER = "recruiter"
JWT_ROLE_HIRING_MANAGER = "hiring_manager"
JWT_ROLE_INTERVIEWER = "interviewer"
JWT_ROLE_VIEWER = "viewer"
JWT_ROLE_CANDIDATE = "candidate"

# UI display (matches Entra app role labels in header).
UI_ROLE_RECRUITER = "RECRUITER"

# Malomatia HR recruitment team — same Entra/DB role as xx1@malomatia.com.
HR_RECRUITER_EMAILS: tuple[str, ...] = (
    "vbhushan@malomatia.com",
    "rcambell@malomatia.com",
    "kpole@malomatia.com",
    "rxavier@malomatia.com",
    "nsahare@malomatia.com",
    "mvismonte@malomatia.com",
    "pdudhnale@malomatia.com",
    "rgirle@malomatia.com",
)

XX1_RECRUITER_EMAIL = "xx1@malomatia.com"

# Entra may emit mixed case; all must normalize to ENTRA_ROLE_RECRUITER.
RECRUITER_ENTRA_INPUT_VARIANTS: tuple[str, ...] = (
    "RECRUITER",
    "Recruiter",
    "RECruiter",
    "recruiter",
    "Recruiter Access",
)
