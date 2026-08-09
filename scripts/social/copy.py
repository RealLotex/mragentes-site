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

from .notas import Nota
from .templates import Piece

# ── Bolsas de texto ─────────────────────────────────────────────────────────

HOOKS = [
    "Nota nueva en el sitio.",
    "Lo escribimos hoy:",
    "Apuntes de esta semana:",
    "Publicamos algo que nos vienen preguntando:",
    "Del cuaderno de esta semana:",
    "Salió nota nueva:",
    "Para leer con un café:",
    "Lo que nos ocupó estos días:",
]

CLOSERS_FB = [
    "Se lee en cinco minutos. El enlace, acá arriba.",
    "Si te toca de cerca, escribinos y lo charlamos sin vueltas.",
    "¿Lo estás viendo en tu operación? Contanos.",
    "Como siempre: sin humo y con las fuentes a la vista.",
    "Comentanos qué harías vos.",
]

CLOSERS_IG = [
    "La nota completa está en el sitio — el enlace está en la bio.",
    "Enlace en la bio para leerla entera.",
    "Está entera en mragentes.com.ar (enlace en la bio).",
    "Te la dejamos completa en el sitio: enlace en la bio.",
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


# ── Textos por red ──────────────────────────────────────────────────────────


def caption(nota: Nota, network: str = "facebook", base_url: str = "https://mragentes.com.ar") -> str:
    seed = seed_for(nota.slug)
    url = nota.url(base_url)
    lead = _trim(nota.lead, 320)
    extra = ""
    paras = nota.paragraphs
    if network == "facebook" and len(paras) > 1:
        extra = "\n\n" + _trim(paras[1] if paras[0] == nota.description else paras[0], 280)

    if network == "instagram":
        body = [
            nota.title,
            "",
            lead,
        ]
        points = [b for b in nota.bullets if len(b) < 110][:3]
        if not points:
            points = [h for h in nota.headings if 15 < len(h) < 90][:3]
        if points:
            body += [""] + [f"· {_trim(p, 110)}" for p in points]
        body += ["", _pick(CLOSERS_IG, seed), "", " ".join(hashtags(nota, seed, 12))]
        return "\n".join(body).strip()

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
        "",
        " ".join(hashtags(nota, seed, 6)),
    ]
    return "\n".join(body).strip()


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
    )


def story_piece(nota: Nota, base_url: str = "https://mragentes.com.ar") -> Piece:
    piece = cover_piece(nota, base_url)
    piece.lead = _trim(nota.lead, 150)
    piece.footer_right = "leé la nota »"
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
        )))

    quotes = [q for q in nota.quotes if 60 <= len(q) <= 240]
    if quotes:
        # Atribución honesta: la frase es de la nota, no nuestra. Poner
        # «MR Agentes» debajo de una cita ajena sería inventar una fuente.
        out.append(("cita", Piece(
            quote=_trim(quotes[seed % len(quotes)], 230),
            author=f"Citado en la nota del {nota.date_label}",
            kicker="cita",
        )))

    headings = [h for h in nota.headings if 12 < len(h) < 90]
    if len(headings) >= 3:
        out.append(("lista", Piece(
            title="Lo que trae la nota",
            items=headings[:4],
            kicker="en tres puntos" if len(headings) == 3 else "de un vistazo",
            cta="La nota completa, en el sitio",
        )))
    elif nota.bullets:
        items = [_trim(b, 100) for b in nota.bullets[:4]]
        n = len(items)
        out.append(("lista", Piece(
            title=(f"{n} cosas para llevarse") if n else "Lo que trae la nota",
            items=items,
            kicker="para tener a mano",
            cta="La nota completa, en el sitio",
        )))

    return out[:limit]


def closing_piece(nota: Nota) -> Piece:
    return Piece(
        title="¿Esto te pasa en tu operación?",
        lead="Automatización de procesos y agentes de IA para pymes. "
             "Primera charla sin cargo: te decimos si conviene y si no, también.",
        kicker="mr agentes",
        rows=[
            ("web", "mragentes.com.ar"),
            ("whatsapp", "3404 50-2729"),
            ("dónde", "Gálvez, Santa Fe · remoto en todo el país"),
        ],
    )


def carousel_for_nota(nota: Nota, base_url: str = "https://mragentes.com.ar", max_slides: int = 4) -> list[tuple[str, Piece]]:
    slides: list[tuple[str, Piece]] = [("nota", cover_piece(nota, base_url))]
    slides += support_pieces(nota, limit=max_slides - 2)
    slides.append(("anuncio", closing_piece(nota)))
    return slides[:max_slides]
