from __future__ import annotations

import re
import shutil
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

from tests.support.contracts import ROOT


def _build(tmp_path: Path, notes: list[tuple[str, str, str]]) -> str:
    """Render the real home with isolated content, including weighted/draft notes."""
    hugo = shutil.which("hugo")
    assert hugo, "Hugo is required to verify the home build"
    (tmp_path / "layouts/partials").mkdir(parents=True)
    (tmp_path / "content/notas").mkdir(parents=True)
    shutil.copyfile(ROOT / "hugo.toml", tmp_path / "hugo.toml")
    shutil.copyfile(ROOT / "layouts/index.html", tmp_path / "layouts/index.html")
    for partial in (ROOT / "layouts/partials").glob("home-*.html"):
        shutil.copyfile(partial, tmp_path / "layouts/partials" / partial.name)
    (tmp_path / "layouts/_default").mkdir()
    shutil.copyfile(ROOT / "layouts/_default/single.html", tmp_path / "layouts/_default/single.html")
    shutil.copyfile(ROOT / "content/nosotros.md", tmp_path / "content/nosotros.md")
    (tmp_path / "layouts/_default/baseof.html").write_text(
        '<main>{{ block "main" . }}{{ end }}</main>', encoding="utf-8"
    )
    (tmp_path / "layouts/partials/closer.html").write_text(
        '<a href="/contacto/">Contame tu caso</a>', encoding="utf-8"
    )
    image_path = tmp_path / "static/images/stock/fixture.png"
    image_path.parent.mkdir(parents=True)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    image_path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1200, 675, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\0" + b"\xa8\x39\x1b" * 1200) * 675))
        + chunk(b"IEND", b"")
    )
    for slug, date, extra in notes:
        (tmp_path / f"content/notas/{slug}.md").write_text(
            f'---\ntitle: "{slug}"\ndate: "{date}"\nslug: "{slug}"\n'
            f'description: "Resumen de {slug}"\n{extra}\n---\nTexto de la nota.\n',
            encoding="utf-8",
        )
    (tmp_path / "content/servicios.md").write_text(
        '---\ntitle: "Servicios"\ndate: "2021-01-01"\n---\nServicios.', encoding="utf-8"
    )
    result = subprocess.run(
        [hugo, "--quiet", "--destination", str(tmp_path / "public")],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    return (tmp_path / "public/index.html").read_text(encoding="utf-8")


@pytest.mark.trace("HOME-NOTES-001")
@pytest.mark.red_expected
@pytest.mark.visual
def test_home_puts_latest_published_notes_between_offer_and_services(tmp_path: Path) -> None:
    image = 'image: "/images/stock/fixture.png"\nimage_alt: "Ilustración de prueba"'
    home = _build(tmp_path, [
        ("old-weighted", "2020-01-01", "weight: 1"),
        ("third", "2020-01-02", image),
        ("second", "2020-01-03", image),
        ("latest", "2020-01-04", image),
        ("draft", "2020-01-05", "draft: true"),
        ("future", "2099-01-01", ""),
    ])
    assert home.index("Contar mi caso") < home.index('id="t-notas"') < home.index('id="t-catalogo"')
    note_links = re.findall(r'href="(/notas/[^\"]+/)"', home)
    assert note_links == ["/notas/latest/", "/notas/second/", "/notas/third/"]
    assert "creationofadam.png" not in home
    assert home.count("<h1>") == 1
    assert home.count('<article class="latest-note') == 3
    assert 'href="/notas/"' in home


@pytest.mark.trace("HOME-NOTES-002")
@pytest.mark.red_expected
@pytest.mark.visual
def test_home_uses_assigned_image_with_responsive_local_derivatives(tmp_path: Path) -> None:
    home = _build(tmp_path, [("latest", "2020-01-01",
        'image: "/images/stock/fixture.png"\nimage_alt: "Ilustración de prueba"')])
    assert 'alt="Ilustración de prueba"' in home
    assert "srcset=" in home and "sizes=" in home
    assert 'width="960" height="540"' in home
    sources = re.findall(r'(/note-images/[^\s\"]+\.webp)', home)
    assert sources, "Home must serve optimized versions of the assigned illustration"
    for source in sources:
        output = tmp_path / "public" / source.lstrip("/")
        assert output.is_file()
        assert output.stat().st_size < 100_000


@pytest.mark.trace("HOME-NOTES-003")
@pytest.mark.red_expected
@pytest.mark.visual
@pytest.mark.parametrize("count", [0, 1, 2])
def test_home_handles_fewer_notes_and_missing_images(tmp_path: Path, count: int) -> None:
    home = _build(tmp_path, [(f"note-{i}", f"2020-01-0{i + 1}", "") for i in range(count)])
    assert home.count('<article class="latest-note') == count
    assert ('id="t-notas"' in home) == (count > 0)
    assert '<img src=""' not in home
    assert 'id="t-catalogo"' in home and 'href="/contacto/"' in home


@pytest.mark.trace("HOME-NOTES-004")
@pytest.mark.red_expected
@pytest.mark.parametrize("workflow", ["ci.yml", "deploy.yml"])
def test_ci_installs_the_production_hugo_before_rendering_contracts(workflow: str) -> None:
    source = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
    python_job = source.split("      - name: Run Python contracts", 1)[0]
    assert "peaceiris/actions-hugo@6e295a6a0c9087bf374299e9d67f9d2edab9f18f" in python_job
    assert 'hugo-version: "0.128.0"' in python_job
    assert "extended: true" in python_job


@pytest.mark.trace("HOME-NOTES-005")
@pytest.mark.red_expected
@pytest.mark.visual
def test_brand_illustration_moves_to_about_with_its_caption(tmp_path: Path) -> None:
    home = _build(tmp_path, [])
    about = (tmp_path / "public/nosotros/index.html").read_text(encoding="utf-8")
    assert "creationofadam.png" not in home
    assert 'src="/creationofadam.png"' in about
    assert "La creación de Adán" in about and "Dominio público" in about
    assert "de ahí sale la mano" in about
    assert 'loading="lazy"' in about
