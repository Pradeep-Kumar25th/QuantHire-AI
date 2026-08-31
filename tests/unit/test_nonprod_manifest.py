"""Non-Prod manifest blocker checks (audit S3, Q3)."""

from pathlib import Path

MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "kubernetes"
    / "nonprod"
    / "quanthire.yaml"
)


def test_both_services_are_internal_loadbalancer():
    content = MANIFEST.read_text(encoding="utf-8")
    backend_section = content.split("name: quanthire-backend", 1)[1].split(
        "name: quanthire-frontend", 1
    )[0]
    frontend_section = content.split("name: quanthire-frontend", 1)[1]
    for section in (backend_section, frontend_section):
        assert "type: LoadBalancer" in section
        assert "azure-load-balancer-internal: \"true\"" in section
    assert "type: ClusterIP" not in backend_section


def test_manifest_uses_current_image_tag():
    content = MANIFEST.read_text(encoding="utf-8")
    assert "quanthire-backend:0.1.5" in content
    assert "quanthire-frontend:0.1.5" in content


def test_manifest_allows_cluster_internal_hosts():
    content = MANIFEST.read_text(encoding="utf-8")
    assert "ALLOWED_HOSTS:" in content
    assert "*.svc.cluster.local" in content
    assert "quanthire-backend.quanthire-nonprod.svc.cluster.local" in content


def test_api_probes_send_localhost_host_header():
    """TrustedHostMiddleware requires Host header; kubelet sends Pod IP by default."""
    content = MANIFEST.read_text(encoding="utf-8")
    api_section = content.split("name: quanthire-nonprod-api", 1)[1].split(
        "name: quanthire-nonprod-web", 1
    )[0]
    assert "httpHeaders:" in api_section
    assert "value: localhost" in api_section
    assert "/healthz" in api_section
    assert "/readyz" in api_section
