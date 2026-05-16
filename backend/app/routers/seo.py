from datetime import datetime, timezone
from html import escape

from fastapi import APIRouter, Request
from fastapi.responses import Response


router = APIRouter(tags=["seo"])


@router.get("/robots.txt", include_in_schema=False)
def robots_txt(request: Request) -> Response:
    base_url = _public_base_url(request)
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /api/",
            "Disallow: /login",
            f"Sitemap: {base_url}/sitemap.xml",
            "",
        ]
    )
    return Response(content=body, media_type="text/plain; charset=utf-8")


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml(request: Request) -> Response:
    base_url = _public_base_url(request)
    lastmod = datetime.now(timezone.utc).date().isoformat()
    urls = [
        {
            "loc": f"{base_url}/",
            "lastmod": lastmod,
            "changefreq": "daily",
            "priority": "1.0",
        }
    ]
    body = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for item in urls:
        body.extend(
            [
                "  <url>",
                f"    <loc>{escape(item['loc'])}</loc>",
                f"    <lastmod>{item['lastmod']}</lastmod>",
                f"    <changefreq>{item['changefreq']}</changefreq>",
                f"    <priority>{item['priority']}</priority>",
                "  </url>",
            ]
        )
    body.append("</urlset>")
    return Response(content="\n".join(body), media_type="application/xml; charset=utf-8")


def _public_base_url(request: Request) -> str:
    proto = (
        (request.headers.get("x-forwarded-proto") or request.url.scheme or "https")
        .split(",")[0]
        .strip()
    )
    host = (
        (
            request.headers.get("x-forwarded-host")
            or request.headers.get("host")
            or request.url.netloc
        )
        .split(",")[0]
        .strip()
    )
    return f"{proto}://{host}".rstrip("/")
