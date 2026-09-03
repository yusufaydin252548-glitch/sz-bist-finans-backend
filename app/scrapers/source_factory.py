"""Bildirim kaynagi secici — Yol A / Yol B arasi tek nokta.

01-faz1 §7: "sıradaki somut adım ... sub-agent zincirini
`get_disclosure_source()` üzerine inşa etmek."

Kullanim:
    from app.scrapers.source_factory import get_disclosure_source

    async with get_disclosure_source() as src:
        cursor = await src.latest_cursor()
        refs = await src.list_new(since=last_cursor)

Kaynak `settings.CONTENT_DATA_SOURCE` ile secilir:
    "borsapy"  → BorsapySource (Yol A / MVP, varsayilan)
    "kap_api"  → KAPApiSource  (Yol B / resmi API, sozlesme sonrasi)
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import get_settings
from app.scrapers.disclosure_source import DisclosureSource

logger = logging.getLogger(__name__)

_ALIASES = {
    "borsapy": "borsapy",
    "yol_a": "borsapy",
    "a": "borsapy",
    "mvp": "borsapy",
    "kap_api": "kap_api",
    "kap": "kap_api",
    "yol_b": "kap_api",
    "b": "kap_api",
    "official": "kap_api",
}


def get_disclosure_source(name: Optional[str] = None) -> DisclosureSource:
    """Yapilandirilmis (veya `name` ile zorlanan) DisclosureSource dondurur."""
    raw = (name or get_settings().CONTENT_DATA_SOURCE or "borsapy").strip().lower()
    key = _ALIASES.get(raw, raw)

    if key == "kap_api":
        from app.scrapers.kap_api_source import KAPApiSource

        logger.info("Bildirim kaynagi: kap_api (Yol B — resmi KAP API)")
        return KAPApiSource()

    if key == "borsapy":
        from app.scrapers.borsapy_source import BorsapySource

        logger.info("Bildirim kaynagi: borsapy (Yol A — MVP)")
        return BorsapySource()

    raise ValueError(
        f"Bilinmeyen CONTENT_DATA_SOURCE={raw!r}. "
        "Gecerli degerler: 'borsapy' (Yol A) | 'kap_api' (Yol B)."
    )
