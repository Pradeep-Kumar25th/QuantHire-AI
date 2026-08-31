#!/usr/bin/env python3
"""Validate Entra SSO readiness for Malomatia HR recruiters (same role as xx1)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
sys.path.insert(0, str(REPO_ROOT / "apps" / "agents" / "agents"))

from app.integrations.entra_auth import (  # noqa: E402
    ENTRA_ROLE_TO_QUANTHIRE,
    _canonical_entra_role_key,
    _identity_from_id_token_claims,
    _pick_quanthire_role,
)
from app.middleware.rbac import UserRole, coerce_user_role
from app.models.users import UserRole as ModelUserRole
from app.repositories.user_loader import role_to_pg_enum_label

# HR team list (Rohan Cambell / Recruitment Team table — Aug 2026).
HR_RECRUITERS: list[tuple[str, str]] = [
    ("vbhushan@malomatia.com", "Vaibhav Bharat Bhushan"),
    ("rcambell@malomatia.com", "Rohan Cambell"),
    ("kpole@malomatia.com", "Ketaki Pole"),  # KPole@malomatia.com → lowercased
    ("rxavier@malomatia.com", "Romin Xavier"),
    ("nsahare@malomatia.com", "Nisha Sahare"),
    ("mvismonte@malomatia.com", "Melanie Carlos Vismonte"),
    ("pdudhnale@malomatia.com", "Pradeep Dudhnale"),
    ("rgirle@malomatia.com", "Richard Duncan Girle"),
]

# Entra app role strings Hazim may assign (Azure manifest value or display name).
RECRUITER_ENTRA_VARIANTS = (
    "RECRUITER",
    "Recruiter",
    "RECruiter",
    "recruiter",
    "Recruiter Access",
)

NPD_CLIENT_ID = "221c7e05-6581-4226-9a08-96a4011dd5ce"
NPD_TENANT_ID = "68bae048-c310-4ec2-934f-cbc2588f30fe"
XX1_EMAIL = "xx1@malomatia.com"


def main() -> int:
    errors: list[str] = []
    checks: list[str] = []

    # --- Role mapping (same chain as xx1) ---
    for variant in RECRUITER_ENTRA_VARIANTS:
        picked = _pick_quanthire_role([variant])
        pg = role_to_pg_enum_label(ModelUserRole(picked.value))
        jwt = picked.value
        if picked != UserRole.RECRUITER or pg != "RECRUITER" or jwt != "recruiter":
            errors.append(f"Recruiter variant {variant!r} failed role chain")
    checks.append(f"Recruiter Entra variants ({len(RECRUITER_ENTRA_VARIANTS)}) → RECRUITER/pg/jwt OK")

    if _pick_quanthire_role(["RECRUITER"]) != _pick_quanthire_role(["Recruiter"]):
        errors.append("RECRUITER and Recruiter must map to the same role")

    # --- Simulated ID token for each HR email ---
    for email, name in HR_RECRUITERS:
        for entra_role in ("RECRUITER", "Recruiter"):
            payload = {
                "oid": f"entra-{email.split('@')[0]}",
                "name": name,
                "preferred_username": email.upper().replace("kpole", "KPole"),  # mixed-case Entra UPN
                "roles": [entra_role],
                "tid": NPD_TENANT_ID,
            }
            identity = _identity_from_id_token_claims(payload)
            if identity["email"] != email:
                errors.append(f"Email normalize failed for {email}: got {identity['email']}")
            if identity["role"] != UserRole.RECRUITER:
                errors.append(f"Role failed for {email} with Entra {entra_role!r}")
            pg = role_to_pg_enum_label(ModelUserRole(identity["role"].value))
            if pg != "RECRUITER":
                errors.append(f"PG label failed for {email}: {pg}")
            coerced = coerce_user_role(identity["role"].value)
            if coerced != UserRole.RECRUITER:
                errors.append(f"coerce_user_role failed for {email}")
    checks.append(f"HR recruiter emails ({len(HR_RECRUITERS)}) → identity/upsert role chain OK")

    # --- xx1 parity ---
    xx1_identity = _identity_from_id_token_claims(
        {
            "oid": "entra-xx1",
            "name": "Test Recruiter",
            "preferred_username": XX1_EMAIL,
            "roles": ["RECRUITER"],
        }
    )
    hr_sample = _identity_from_id_token_claims(
        {
            "oid": "entra-rcambell",
            "name": "Rohan Cambell",
            "preferred_username": "rcambell@malomatia.com",
            "roles": ["Recruiter"],
        }
    )
    if xx1_identity["role"] != hr_sample["role"]:
        errors.append("xx1 and HR recruiter roles differ")
    if role_to_pg_enum_label(ModelUserRole(xx1_identity["role"].value)) != "RECRUITER":
        errors.append("xx1 PG role is not RECRUITER")
    checks.append("xx1@malomatia.com parity with HR recruiters OK")

    # --- Provision script sync ---
    provision_py = (REPO_ROOT / "apps" / "api" / "scripts" / "provision_hr_recruiters.py").read_text(
        encoding="utf-8"
    )
    for email, _name in HR_RECRUITERS:
        if email not in provision_py:
            errors.append(f"provision_hr_recruiters.py missing {email}")
    checks.append("provision_hr_recruiters.py contains all 8 emails")

    # --- Static wiring (frontend + k8s) ---
    k8s = (REPO_ROOT / "infra" / "kubernetes" / "nonprod" / "quanthire.yaml").read_text(
        encoding="utf-8"
    )
    for needle in (NPD_CLIENT_ID, NPD_TENANT_ID, "quanthire-npd.malomatia.com"):
        if needle not in k8s:
            errors.append(f"quanthire.yaml missing {needle}")
    checks.append("NPD k8s Entra client/tenant + host OK")

    msal = (REPO_ROOT / "apps" / "web" / "src" / "lib" / "msal-auth.ts").read_text(encoding="utf-8")
    for needle in ("loginPopup", 'prompt: "login"', "sso-config", "window.location.origin"):
        if needle not in msal:
            errors.append(f"msal-auth.ts missing {needle}")
    checks.append("MSAL loginPopup + redirect URI (origin) OK")

    auth_provider = (
        REPO_ROOT / "apps" / "web" / "src" / "contexts" / "auth-provider.tsx"
    ).read_text(encoding="utf-8")
    for needle in ("/v1/auth/entra/callback", "/v1/auth/me", "loginWithMicrosoft"):
        if needle not in auth_provider:
            errors.append(f"auth-provider missing {needle}")
    checks.append("Frontend Entra callback + /me verification OK")

    auth_py = (REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "auth.py").read_text(
        encoding="utf-8"
    )
    for needle in ("/entra/callback", "_upsert_entra_user", "attach_session_cookies"):
        if needle not in auth_py:
            errors.append(f"auth.py missing {needle}")
    checks.append("Backend Entra callback + cookie session OK")

    entra_py = (
        REPO_ROOT / "apps" / "api" / "app" / "integrations" / "entra_auth.py"
    ).read_text(encoding="utf-8")
    if "_canonical_entra_role_key" not in entra_py:
        errors.append("entra_auth.py missing _canonical_entra_role_key (deploy role normalization fix)")

    # --- Entra manifest role keys ---
    if ENTRA_ROLE_TO_QUANTHIRE.get("RECRUITER") != UserRole.RECRUITER:
        errors.append("ENTRA_ROLE_TO_QUANTHIRE missing RECRUITER")

    if errors:
        print("HR RECRUITER SSO VALIDATION FAILED:")
        for err in errors:
            print(f"  ✗ {err}")
        return 1

    print("HR RECRUITER SSO VALIDATION PASSED")
    for item in checks:
        print(f"  ✓ {item}")
    print()
    print("Entra-side (Hazim): assign app role Recruiter/RECRUITER to all 8 @malomatia.com users.")
    print("App-side: optional — python apps/api/scripts/provision_hr_recruiters.py on NPD API pod.")
    print("Login URL: https://quanthire-npd.malomatia.com/login → Sign in with Microsoft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
