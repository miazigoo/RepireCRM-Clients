from fastapi.testclient import TestClient


def test_robots_txt_points_to_public_sitemap(client: TestClient) -> None:
    r = client.get(
        "/robots.txt",
        headers={"host": "repire-status.ru", "x-forwarded-proto": "https"},
    )
    assert r.status_code == 200
    assert "User-agent: *" in r.text
    assert "Disallow: /api/" in r.text
    assert "Disallow: /login" in r.text
    assert "Sitemap: https://repire-status.ru/sitemap.xml" in r.text


def test_sitemap_xml_uses_forwarded_host(client: TestClient) -> None:
    r = client.get(
        "/sitemap.xml",
        headers={"host": "repire-status.ru", "x-forwarded-proto": "https"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    assert "<loc>https://repire-status.ru/</loc>" in r.text
    assert "<priority>1.0</priority>" in r.text
    assert "/login" not in r.text
