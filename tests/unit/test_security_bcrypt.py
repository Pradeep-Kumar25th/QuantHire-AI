"""Password hashing must not import passlib at runtime (bcrypt 5.x crash)."""


def test_get_password_hash_and_verify_roundtrip():
    from app.core.security import get_password_hash, verify_password

    hashed = get_password_hash("ChangeMe123!")
    assert hashed.startswith("$2")
    assert verify_password("ChangeMe123!", hashed)
    assert not verify_password("wrong-password", hashed)


def test_auth_module_imports_without_passlib_crash():
    """Regression: module-level passlib init crashed API startup on bcrypt 5.x."""
    import importlib

    import app.api.v1.auth as auth_module

    importlib.reload(auth_module)
    assert auth_module.router is not None
