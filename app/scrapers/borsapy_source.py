"""Yol A (MVP) — borsapy uzerinden bildirim kaynagi.

01-faz1-sub-agent-icerik-motoru.md §2 Yol A + §6.3:
    `bp.Ticker(symbol).news`  → KAP bildirimleri (borsapy sarmalıyor)
    `bp.Ticker(symbol).info["sector"]` → sektor eslemesi
    `bp.Index("XU100").components`     → takip evreni

borsapy tek kutuphaneden hem bildirim hem sektor hem fiyat verdigi icin
MVP asamasinda birincil kaynak (bkz. §4 "Oneri"). Sozlesme + kurumsal
kimlik tamamlaninca `CONTENT_DATA_SOURCE=kap_api` ile Yol B'ye gecilir.

NOT (§6.3): borsapy lisansi "kisisel/egitim amacli" — platform gercek
kullanicilara acilan ticari bir servise donusurse Borsa Istanbul ile
lisans gorusmesi gerekir. Bu modul kutuphaneyi opsiyonel tutar: kurulu
degilse net bir hata verir, uygulama acilisini kirmaz.

Kurulum:  pip install -r requirements-content.txt
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from app.scrapers.disclosure_source import (
    DisclosureContent,
    DisclosureRef,
    DisclosureSource,
)

logger = logging.getLogger(__name__)

_COLD_START_DAYS = 3
_DEFAULT_UNIVERSE_INDEX = "XU100"
# borsapy hic yoksa / evren cekilemezse son care mini liste.
_FALLBACK_UNIVERSE = ["THYAO", "GARAN", "AKBNK", "ASELS", "SISE", "KCHOL", "SASA", "EREGL"]

_INSTALL_HINT = (
    "borsapy kurulu degil. Yol A (CONTENT_DATA_SOURCE=borsapy) icin gerekli: "
    "pip install -r requirements-content.txt  —  veya CONTENT_DATA_SOURCE=kap_api kullanin."
)


def _load_borsapy():
    """borsapy'yi lazy import eder (opsiyonel bagimlilik)."""
    try:
        import borsapy as bp  # type: ignore
    except ImportError as exc:  # pragma: no cover - ortam bagimli
        raise RuntimeError(_INSTALL_HINT) from exc
    return bp


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_dt(value) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:  # pandas.Timestamp veya ISO string
        import pandas as pd  # type: ignore

        ts = pd.to_datetime(value, utc=True, errors="coerce")
        return None if ts is None or pd.isna(ts) else ts.to_pydatetime()
    except Exception:  # noqa: BLE001
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(str(value)[:19], fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _rows(obj) -> list[dict]:
    """borsapy `.news` ciktisini (DataFrame | list | None) dict listesine cevirir."""
    if obj is None:
        return []
    if isinstance(obj, list):
        return [r for r in obj if isinstance(r, dict)]
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        try:
            return obj.to_dict(orient="records")  # DataFrame
        except TypeError:
            pass
    return []


class BorsapySource(DisclosureSource):
    """DisclosureSource implementasyonu — borsapy (Yol A / MVP)."""

    name = "borsapy"

    def __init__(self, tickers: Optional[Iterable[str]] = None):
        self._bp = None
        self._universe: list[str] = [t.upper() for t in tickers] if tickers else []
        self._sector_cache: dict[str, tuple[Optional[str], Optional[str]]] = {}

    def _bp_mod(self):
        if self._bp is None:
            self._bp = _load_borsapy()
        return self._bp

    async def _universe_tickers(self) -> list[str]:
        if self._universe:
            return self._universe

        def _fetch() -> list[str]:
            bp = self._bp_mod()
            try:
                comp = bp.Index(_DEFAULT_UNIVERSE_INDEX).components
                if hasattr(comp, "tolist"):
                    comp = comp.tolist()
                elif hasattr(comp, "index"):
                    comp = list(comp.index)
                out = [str(c).upper() for c in comp if c]
                if out:
                    return out
            except Exception as exc:  # noqa: BLE001
                logger.warning("borsapy evren cekilemedi (%s) — fallback listesi", exc)
            return list(_FALLBACK_UNIVERSE)

        self._universe = await asyncio.to_thread(_fetch)
        logger.info("BorsapySource evren: %d hisse", len(self._universe))
        return self._universe

    # -- kesif --------------------------------------------------------------

    async def latest_cursor(self) -> str:
        return _now_utc().isoformat()

    async def list_new(
        self, since: Optional[str], *, limit: int = 50
    ) -> list[DisclosureRef]:
        cutoff = (
            _coerce_dt(since)
            if since
            else _now_utc() - timedelta(days=_COLD_START_DAYS)
        )
        tickers = await self._universe_tickers()

        def _collect() -> list[DisclosureRef]:
            bp = self._bp_mod()
            found: list[DisclosureRef] = []
            for tk in tickers:
                try:
                    news = bp.Ticker(tk).news
                except Exception as exc:  # noqa: BLE001 — tek hisse hatasi tumunu durdurmasin
                    logger.debug("borsapy %s .news hatasi: %s", tk, exc)
                    continue
                for row in _rows(news):
                    # TEYIT: alan adlari borsapy surumune gore degisebilir.
                    published = _coerce_dt(
                        row.get("date") or row.get("datetime") or row.get("published")
                    )
                    if cutoff and published and published <= cutoff:
                        continue
                    link = row.get("link") or row.get("url") or ""
                    ref_id = str(link or row.get("id") or f"{tk}:{published}")
                    found.append(
                        DisclosureRef(
                            source_ref=ref_id,
                            source="borsapy",
                            title=(row.get("title") or row.get("headline") or "").strip(),
                            stock_code=tk,
                            published_at=published,
                            url=link or None,
                            extra={"raw": row},
                        )
                    )
            found.sort(key=lambda r: r.published_at or _now_utc())
            return found[:limit]

        refs = await asyncio.to_thread(_collect)
        logger.info("BorsapySource.list_new: %d bildirim (cutoff=%s)", len(refs), cutoff)
        return refs

    async def fetch_detail(self, ref: DisclosureRef) -> DisclosureContent:
        # Yol A'da `.news` satiri genelde ozeti/icerigi zaten tasir; ayri bir
        # detay endpoint'i yok. Elimizdeki alanlari DisclosureContent'e tasiriz.
        raw = ref.extra.get("raw") or {}
        body = (
            raw.get("content")
            or raw.get("summary")
            or raw.get("description")
            or raw.get("text")
            or ""
        )
        return DisclosureContent(
            ref=ref,
            summary=raw.get("summary") or raw.get("description") or ref.title,
            raw_html=body if "<" in body else "",
            clean_text="" if "<" in body else body,
            published_at=ref.published_at,
            url=ref.url,
            extra={"raw": raw},
        )

    # -- sektor eslemesi (§6.1.1: KAP sektor vermiyor) -------------------

    async def sector_for(self, ticker: str) -> tuple[Optional[str], Optional[str]]:
        """(sector_name, industry) — borsapy `Ticker.info`'dan. Cache'li."""
        tk = (ticker or "").upper()
        if not tk:
            return None, None
        if tk in self._sector_cache:
            return self._sector_cache[tk]

        def _fetch() -> tuple[Optional[str], Optional[str]]:
            try:
                info = self._bp_mod().Ticker(tk).info or {}
                return info.get("sector"), info.get("industry")
            except Exception as exc:  # noqa: BLE001
                logger.debug("borsapy %s sektor hatasi: %s", tk, exc)
                return None, None

        result = await asyncio.to_thread(_fetch)
        self._sector_cache[tk] = result
        return result
