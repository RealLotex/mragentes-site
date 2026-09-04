"""
El texto del posteo.

Tres decisiones, todas contra el mismo problema: que no parezcan todos el
mismo posteo.

  1. El gancho, el cierre y el juego de etiquetas salen de bolsas que rotan
     con una semilla derivada del slug de la nota: distinto en cada nota,
     pero siempre igual para la misma nota (rehacer un posteo no lo cambia).
  2. Facebook e Instagram no reciben el mismo texto. En Facebook el enlace es
     un enlace; en Instagram no se puede tocar, así que el cierre es otro.
  3. De cada nota se sacan además materiales para las láminas de apoyo — un
     número, una cita, los subtítulos — y con eso se arma el carrusel. Ahí
     está la diferencia entre un aviso y un posteo que se lee solo.
"""

from __future__ import annotations

import hashlib
import re

from . import brand
from .notas import Nota
from .templates import Piece

# ── Bolsas de texto ─────────────────────────────────────────────────────────

HOOKS = [
    "Una guía nueva para empezar:",
    "Una idea explicada paso a paso:",
    "Nueva nota para entender el tema desde cero:",
    "Una explicación práctica para empezar:",
]

# Es el mismo CTA visible en las láminas. Mantenerlo como constante evita que
# el texto del posteo y la pieza gráfica prometan acciones distintas.
SOCIAL_SHARE_CTA = brand.SOCIAL_SHARE_CTA

CLOSERS_FB = [
    "La nota completa explica los conceptos y muestra un primer paso posible.",
    "Las fuentes y las preguntas frecuentes están al final de la nota.",
    "El artículo completo está disponible en el sitio.",
]

CLOSERS_IG = [
    "La nota completa explica el tema paso a paso; el enlace está en la bio.",
    "La nota completa y las fuentes están en mragentes.com.ar; enlace en la bio.",
    "Si recién empieza con este tema, la guía completa está en la bio.",
]

TAG_MAP = {
    "ia": "InteligenciaArtificial",
    "ai": "InteligenciaArtificial",
    "automatizacion": "Automatizacion",
    "automatización": "Automatizacion",
    "agentes": "AgentesDeIA",
    "chatbots": "Chatbots",
    "atencion-al-cliente": "AtencionAlCliente",
    "regulacion": "RegulacionIA",
    "ley-ia": "LeyDeIA",
    "productividad": "Productividad",
    "datos": "Datos",
    "guia": "Guia",
    "principiantes": "ParaEmpezar",
    "tendencias": "Tendencias",
    "empleo": "FuturoDelTrabajo",
    "transformacion-digital": "TransformacionDigital",
    "pymes": "Pymes",
    "negocios": "Negocios",
    "empresas": "Empresas",
    "analisis": "Analisis",
}

BASE_TAGS = ["MRAgentes"]

ROTATING_TAGS = [
    "IAparaPymes",
    "AutomatizacionDeProcesos",
    "TransformacionDigital",
    "Galvez",
    "SantaFe",
    "Argentina",
    "Pymes",
    "AgentesDeIA",
    "NegociosConIA",
    "Productividad",
]

PLATFORM_LIMITS = {"facebook": 63_206, "instagram": 2_200}


def seed_for(text: str) -> int:
    return int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16)


def _pick(bag: list, seed: int, offset: int = 0):
    return bag[(seed + offset) % len(bag)]


def hashtag(tag: str) -> str:
    key = tag.strip().lower()
    if key in TAG_MAP:
        return TAG_MAP[key]
    parts = re.split(r"[^0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", key)
    return "".join(p.capitalize() for p in parts if p)


def hashtags(nota: Nota, seed: int, limit: int = 10) -> list[str]:
    out = list(BASE_TAGS)
    for tag in nota.tags:
        h = hashtag(tag)
        if h and h not in out:
            out.append(h)
    i = 0
    while len(out) < limit and i < len(ROTATING_TAGS) * 2:
        candidate = ROTATING_TAGS[(seed + i) % len(ROTATING_TAGS)]
        if candidate not in out:
            out.append(candidate)
        i += 1
    return [f"#{t}" for t in out[:limit]]


def _trim(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:.")
    return cut + "…"


def _clip_caption(text: str, limit: int) -> str:
    """Recorta un copy completo sin dejar un sustituto Unicode incompleto."""
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rstrip()
    while cut and 0xD800 <= ord(cut[-1]) <= 0xDBFF:
        cut = cut[:-1]
    boundary = max(cut.rfind("\n"), cut.rfind(" "))
    if boundary >= int(limit * 0.75):
        cut = cut[:boundary].rstrip()
    return cut + "…"


def _validate_claims(nota: Nota) -> None:
    """Impide convertir una promesa comercial cuantificada en copy sin fuente."""
    promotional = f"{nota.title}\n{nota.description}"
    quantified = re.search(
        r"(?:\b\d+(?:[.,]\d+)?\s*%|\b\d+(?:[.,]\d+)?\s*(?:x|veces)\b|"
        r"\b(?:duplicar|triplicar)\b)",
        promotional,
        re.I,
    )
    promise = re.search(
        r"\b(?:garantizamos?|aseguramos?|sin riesgo|resultados? garantizados?)\b",
        promotional,
        re.I,
    )
    sourced = bool(
        re.search(r"\[[^\]]+\]\(https?://", nota.body, re.I)
        or re.search(r"^##+\s*(?:Fuentes?|Referencias)\s*$", nota.body, re.I | re.M)
    )
    if (quantified or promise) and not sourced:
        raise ValueError("Afirmación de rendimiento sin fuente ni evidencia verificable")


# ── Textos por red ──────────────────────────────────────────────────────────


def tracked_note_url(nota: Nota, network: str, base_url: str = "https://mragentes.com.ar") -> str:
    """URL de red que registra sólo fuente y nota antes de ir a la guía.

    El Worker de métricas descarta todo dato personal y redirige inmediatamente
    al permalink canónico. No se usan UTMs: Web Analytics no registra queries.
    """
    if network not in PLATFORM_LIMITS:
        raise ValueError("Red/network inválida: sólo facebook o instagram")
    origin = base_url.rstrip("/")
    slug = __import__("urllib.parse").parse.quote(nota.slug, safe="-")
    return f"{origin}/r/{slug}?source={network}"


def caption(nota: Nota, network: str = "facebook", base_url: str = "https://mragentes.com.ar") -> str:
    if network not in PLATFORM_LIMITS:
        raise ValueError("Red/network inválida: sólo facebook o instagram")
    _validate_claims(nota)
    seed = seed_for(nota.slug)
    url = tracked_note_url(nota, network, base_url)
    lead = _trim(nota.lead, 320)
    extra = ""
    paras = nota.paragraphs
    if network == "facebook" and len(paras) > 1:
        extra = "\n\n" + _trim(paras[1] if paras[0] == nota.description else paras[0], 280)

    if network == "instagram":
        body = [
            _trim(nota.title, 420),
            "",
            lead,
        ]
        points = [b for b in nota.bullets if len(b) < 110][:3]
        if not points:
            points = [h for h in nota.headings if 15 < len(h) < 90][:3]
        if points:
            body += [""] + [f"· {_trim(p, 110)}" for p in points]
        body += [
            "",
            _pick(CLOSERS_IG, seed),
            "Enlace en la bio.",
            SOCIAL_SHARE_CTA,
            "",
            " ".join(hashtags(nota, seed, 12)),
        ]
        return _clip_caption("\n".join(body).strip(), PLATFORM_LIMITS[network])

    body = [
        _pick(HOOKS, seed),
        "",
        nota.title,
        "",
        lead + extra,
        "",
        f"Leé la nota completa: {url}",
        "",
        _pick(CLOSERS_FB, seed, 1),
        SOCIAL_SHARE_CTA,
        "",
        " ".join(hashtags(nota, seed, 6)),
    ]
    return _clip_caption("\n".join(body).strip(), PLATFORM_LIMITS[network])


# ── Piezas gráficas derivadas de la nota ────────────────────────────────────


def cover_piece(nota: Nota, base_url: str = "https://mragentes.com.ar") -> Piece:
    return Piece(
        title=nota.title,
        lead=_trim(nota.lead, 190),
        kicker="nota nueva",
        meta=nota.date_label,
        tags=nota.tags,
        photo=str(nota.photo) if nota.photo else None,
        url=nota.url(base_url),
        section="nota nueva",
        footer_right=SOCIAL_SHARE_CTA,
    )


def story_piece(nota: Nota, base_url: str = "https://mragentes.com.ar") -> Piece:
    piece = cover_piece(nota, base_url)
    piece.lead = _trim(nota.lead, 150)
    piece.footer_right = SOCIAL_SHARE_CTA
    return piece


def support_pieces(nota: Nota, limit: int = 3) -> list[tuple[str, Piece]]:
    """Láminas de apoyo del carrusel, según lo que la nota realmente tenga."""
    seed = seed_for(nota.slug)
    out: list[tuple[str, Piece]] = []

    numbers = nota.numbers
    if numbers:
        value, sentence = numbers[seed % len(numbers)]
        # El epígrafe se queda con la primera parte de la frase y el cuerpo con
        # el resto: partirla así evita el error de leer dos veces lo mismo,
        # que es lo que pasaba cuando ambos salían de la frase entera.
        clauses = [c.strip() for c in re.sub(r"\s+", " ", sentence).split(",") if c.strip()]
        head, used = (clauses[0] if clauses else sentence), 1
        while len(head) < 34 and used < len(clauses):
            head = f"{head}, {clauses[used]}"
            used += 1
        tail = ", ".join(clauses[used:]).strip(" ,;:")
        out.append(("dato", Piece(
            stat=value,
            caption=_trim(head, 95),
            lead=_trim(tail, 210) if len(tail) > 45 else "",
            kicker="el dato",
            author="Fuente: la nota completa en mragentes.com.ar",
            footer_right=SOCIAL_SHARE_CTA,
        )))

    quotes = [q for q in nota.quotes if 60 <= len(q) <= 240]
    if quotes:
        # Atribución honesta: la frase es de la nota, no nuestra. Poner
        # «MR Agentes» debajo de una cita ajena sería inventar una fuente.
        out.append(("cita", Piece(
            quote=_trim(quotes[seed % len(quotes)], 230),
            author=f"Citado en la nota del {nota.date_label}",
            kicker="cita",
            footer_right=SOCIAL_SHARE_CTA,
        )))

    headings = [h for h in nota.headings if 12 < len(h) < 90]
    if len(headings) >= 3:
        out.append(("lista", Piece(
            title="Lo que trae la nota",
            items=headings[:4],
            kicker="en tres puntos" if len(headings) == 3 else "de un vistazo",
            cta="La nota completa, en el sitio",
            footer_right=SOCIAL_SHARE_CTA,
        )))
    elif nota.bullets:
        items = [_trim(b, 100) for b in nota.bullets[:4]]
        n = len(items)
        out.append(("lista", Piece(
            title=(f"{n} cosas para llevarse") if n else "Lo que trae la nota",
            items=items,
            kicker="para tener a mano",
            cta="La nota completa, en el sitio",
            footer_right=SOCIAL_SHARE_CTA,
        )))

    return out[:limit]


def closing_piece(nota: Nota) -> Piece:
    return Piece(
        title="¿Esto te pasa en tu empresa?",
        lead="Automatización de procesos y agentes de IA para pymes. "
             "Primera charla sin cargo: te decimos si conviene y si no, también.",
        kicker="mr agentes",
        rows=[
            ("web", "mragentes.com.ar"),
            ("whatsapp", "3404 50-2729"),
            ("dónde", "Gálvez, Santa Fe · remoto en todo el país"),
        ],
        footer_right=SOCIAL_SHARE_CTA,
    )


def carousel_for_nota(nota: Nota, base_url: str = "https://mragentes.com.ar", max_slides: int = 4) -> list[tuple[str, Piece]]:
    if isinstance(max_slides, bool) or not isinstance(max_slides, int) or max_slides < 2:
        raise ValueError("max_slides debe permitir al menos dos láminas")
    slides: list[tuple[str, Piece]] = [("nota", cover_piece(nota, base_url))]
    slides += support_pieces(nota, limit=max_slides - 2)
    slides.append(("anuncio", closing_piece(nota)))
    for _, piece in slides:
        piece.footer_right = SOCIAL_SHARE_CTA
    return slides[:max_slides]


def method_carousel(title: str, methods: list[tuple[str, str]], *, kicker: str = "guía simple") -> list[tuple[str, Piece]]:
    """Crea una portada y una lámina pedagógica por cada método.

    Los métodos se mantienen deliberadamente entre dos y seis: menos no forma
    un carrusel útil y más obliga a comprimir el texto o a perder el hilo.
    """
    if not isinstance(title, str) or not title.strip():
        raise ValueError("El carrusel necesita un título")
    if not 2 <= len(methods) <= 6:
        raise ValueError("El carrusel necesita entre 2 y 6 métodos")
    slides: list[tuple[str, Piece]] = [(
        "punto",
        Piece(
            title=title.strip(),
            lead="Una guía simple: un paso por lámina.",
            kicker=kicker,
            stat=f"{len(methods):02d}",
            footer_right=SOCIAL_SHARE_CTA,
        ),
    )]
    for index, method in enumerate(methods, start=1):
        if not isinstance(method, (tuple, list)) or len(method) != 2:
            raise ValueError("Cada método debe incluir título y explicación")
        name, explanation = (str(method[0]).strip(), str(method[1]).strip())
        if not name or not explanation:
            raise ValueError("Cada método debe incluir título y explicación")
        slides.append(("metodo", Piece(
            title=name,
            lead=explanation,
            kicker=f"método {index} de {len(methods)}",
            stat=f"{index:02d}",
            footer_right=SOCIAL_SHARE_CTA,
        )))
    return slides
