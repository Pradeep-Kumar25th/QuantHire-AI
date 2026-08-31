#!/usr/bin/env python3
"""Static validation for Entra SSO implementation (run before deploy)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
sys.path.insert(0, str(REPO_ROOT / "apps" / "agents" / "agents"))

from app.core.role_labels import HR_RECRUITER_EMAILS, XX1_RECRUITER_EMAIL
from app.integrations.entra_auth import ENTRA_ROLE_TO_QUANTHIRE, _pick_quanthire_role
from app.models.users import UserRole
from app.repositories.user_loader import PG_USERROLE_LABELS, role_to_pg_enum_label

NPD_CLIENT_ID = "221c7e05-6581-4226-9a08-96a4011dd5ce"
NPD_TENANT_ID = "68bae048-c310-4ec2-934f-cbc2588f30fe"
HAZIM_TEST_USERS = {
    "xx1@malomatia.com": ("RECRUITER", "RECRUITER"),
    "xx2@malomatia.com": ("HIRING_MANAGER", "HIRING_MANAGER"),
    "xx3@malomatia.com": ("INTERVIEWER", "INTERVIEWER"),
    "xx4@malomatia.com": ("VIEWER", "viewer"),
    "prakumar@malomatia.com": ("ADMIN", "ADMIN"),
}


def main() -> int:
    errors: list[str] = []

    expected_pg = {
        UserRole.ADMIN: "ADMIN",
        UserRole.RECRUITER: "RECRUITER",
        UserRole.HIRING_MANAGER: "HIRING_MANAGER",
        UserRole.INTERVIEWER: "INTERVIEWER",
        UserRole.VIEWER: "viewer",
        UserRole.CANDIDATE: "CANDIDATE",
    }
    if PG_USERROLE_LABELS != expected_pg:
        errors.append(f"PG_USERROLE_LABELS mismatch: {PG_USERROLE_LABELS}")

    for entra_name, rbac_role in ENTRA_ROLE_TO_QUANTHIRE.items():
        picked = _pick_quanthire_role([entra_name])
        if picked != rbac_role:
            errors.append(f"Entra role pick failed for {entra_name}")
        pg_label = role_to_pg_enum_label(rbac_role)
        if pg_label != expected_pg[UserRole(rbac_role.value)]:
            errors.append(
                f"Entra {entra_name} → rbac {rbac_role.value} → pg {pg_label} (unexpected)"
            )

    for email, (entra_role, pg_label) in HAZIM_TEST_USERS.items():
        model_role = UserRole(_pick_quanthire_role([entra_role]).value)
        if role_to_pg_enum_label(model_role) != pg_label:
            errors.append(f"Hazim user chain failed for {email}")

    xx1_pg = role_to_pg_enum_label(UserRole(_pick_quanthire_role(["RECRUITER"]).value))
    if xx1_pg != "RECRUITER":
        errors.append(f"xx1 PG role must be RECRUITER, got {xx1_pg}")

    for email in HR_RECRUITER_EMAILS:
        hr_role = _pick_quanthire_role(["RECRUITER"])
        if role_to_pg_enum_label(UserRole(hr_role.value)) != xx1_pg:
            errors.append(f"HR recruiter {email} role chain differs from xx1")
    if XX1_RECRUITER_EMAIL not in HAZIM_TEST_USERS:
        errors.append("HAZIM_TEST_USERS must include xx1@malomatia.com")

    auth_py = (REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "auth.py").read_text(
        encoding="utf-8"
    )
    for needle in (
        "role_to_pg_enum_label",
        "CAST(:role AS userrole)",
        "/entra/callback",
        "authenticate_entra_id_token",
        "_upsert_entra_user",
    ):
        if needle not in auth_py:
            errors.append(f"auth.py missing expected SSO fragment: {needle}")

    entra_py = (
        REPO_ROOT / "apps" / "api" / "app" / "integrations" / "entra_auth.py"
    ).read_text(encoding="utf-8")
    for needle in ("ENTRA_ROLE_TO_QUANTHIRE", "roles", "leeway=60", "tenant mismatch"):
        if needle not in entra_py:
            errors.append(f"entra_auth.py missing expected fragment: {needle}")

    msal_ts = (REPO_ROOT / "apps" / "web" / "src" / "lib" / "msal-auth.ts").read_text(
        encoding="utf-8"
    )
    for needle in ("loginPopup", "prompt: \"login\"", "sso-config"):
        if needle not in msal_ts:
            errors.append(f"msal-auth.ts missing expected fragment: {needle}")

    auth_provider = (
        REPO_ROOT / "apps" / "web" / "src" / "contexts" / "auth-provider.tsx"
    ).read_text(encoding="utf-8")
    for needle in ("/v1/auth/entra/callback", "/v1/auth/me"):
        if needle not in auth_provider:
            errors.append(f"auth-provider.tsx missing expected fragment: {needle}")

    api_client = (REPO_ROOT / "apps" / "web" / "src" / "lib" / "api-client.ts").read_text(
        encoding="utf-8"
    )
    if "credentials: \"include\"" not in api_client:
        errors.append("api-client.ts missing credentials: include for cookie-based SSO")

    k8s_yaml = (REPO_ROOT / "infra" / "kubernetes" / "nonprod" / "quanthire.yaml").read_text(
        encoding="utf-8"
    )
    if NPD_CLIENT_ID not in k8s_yaml:
        errors.append(f"quanthire.yaml missing AZURE_AD_CLIENT_ID {NPD_CLIENT_ID}")
    if NPD_TENANT_ID not in k8s_yaml:
        errors.append(f"quanthire.yaml missing AZURE_AD_TENANT_ID {NPD_TENANT_ID}")
    if "quanthire-backend:0.1.5" not in k8s_yaml:
        errors.append("quanthire.yaml backend image tag should be quanthire-backend:0.1.5")

    if errors:
        print("SSO validation FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("SSO validation OK — all Entra/PostgreSQL/frontend/k8s checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
