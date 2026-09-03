from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GATEWAY = ROOT / ".railway-deploy" / "ib-gateway"


def test_railway_ib_gateway_packaging():
    dockerfile = (GATEWAY / "Dockerfile").read_text(encoding="utf-8")
    assert "ghcr.io/gnzsnz/ib-gateway" in dockerfile
    railway = (GATEWAY / "railway.toml").read_text(encoding="utf-8")
    assert 'name = "ib-gateway"' in railway
    assert "READ_ONLY_API" in railway
