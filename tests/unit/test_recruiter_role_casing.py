"""Lock RECRUITER role casing chain for xx1 and all 8 HR recruiters."""

import pytest

from app.core.role_labels import (
    ENTRA_ROLE_RECRUITER,
    HR_RECRUITER_EMAILS,
    JWT_ROLE_RECRUITER,
    PG_ENUM_RECRUITER,
    RECRUITER_ENTRA_INPUT_VARIANTS,
    UI_ROLE_RECRUITER,
    XX1_RECRUITER_EMAIL,
)
from app.integrations.entra_auth import (
    ENTRA_ROLE_TO_QUANTHIRE,
    _canonical_entra_role_key,
    _identity_from_id_token_claims,
    _pick_quanthire_role,
)
from app.middleware.rbac import UserRole, coerce_user_role
from app.models.users import UserRole as ModelUserRole
from app.repositories.user_loader import role_from_pg_enum_label, role_to_pg_enum_label


def test_canonical_recruiter_constants():
    assert ENTRA_ROLE_RECRUITER == "RECRUITER"
    assert PG_ENUM_RECRUITER == "RECRUITER"
    assert JWT_ROLE_RECRUITER == "recruiter"
    assert UI_ROLE_RECRUITER == "RECRUITER"


def test_entra_map_uses_uppercase_recruiter_key():
    assert ENTRA_ROLE_TO_QUANTHIRE[ENTRA_ROLE_RECRUITER] == UserRole.RECRUITER


@pytest.mark.parametrize("variant", RECRUITER_ENTRA_INPUT_VARIANTS)
def test_all_recruiter_entra_variants_normalize_to_recruiter(variant):
    assert _canonical_entra_role_key(variant) in (ENTRA_ROLE_RECRUITER, "RECRUITER_ACCESS")
    assert _pick_quanthire_role([variant]) == UserRole.RECRUITER


def test_xx1_full_role_chain():
    identity = _identity_from_id_token_claims(
        {
            "oid": "entra-xx1",
            "name": "Test Recruiter",
            "preferred_username": XX1_RECRUITER_EMAIL,
            "roles": [ENTRA_ROLE_RECRUITER],
        }
    )
    assert identity["email"] == XX1_RECRUITER_EMAIL
    assert identity["role"] == UserRole.RECRUITER
    assert identity["role"].value == JWT_ROLE_RECRUITER
    assert role_to_pg_enum_label(ModelUserRole(JWT_ROLE_RECRUITER)) == PG_ENUM_RECRUITER
    assert role_from_pg_enum_label(PG_ENUM_RECRUITER) == ModelUserRole.RECRUITER
    assert coerce_user_role(JWT_ROLE_RECRUITER) == UserRole.RECRUITER
    assert coerce_user_role(ENTRA_ROLE_RECRUITER) == UserRole.RECRUITER


@pytest.mark.parametrize("email", HR_RECRUITER_EMAILS)
def test_hr_recruiter_matches_xx1_role_chain(email):
    xx1 = _identity_from_id_token_claims(
        {
            "oid": "entra-xx1",
            "preferred_username": XX1_RECRUITER_EMAIL,
            "roles": [ENTRA_ROLE_RECRUITER],
        }
    )
    hr = _identity_from_id_token_claims(
        {
            "oid": f"entra-{email.split('@')[0]}",
            "preferred_username": email,
            "roles": ["Recruiter"],  # HR table uses title case
        }
    )
    assert hr["role"] == xx1["role"] == UserRole.RECRUITER
    assert role_to_pg_enum_label(hr["role"]) == PG_ENUM_RECRUITER
    assert hr["role"].value == JWT_ROLE_RECRUITER


def test_hr_recruiter_count():
    assert len(HR_RECRUITER_EMAILS) == 8
