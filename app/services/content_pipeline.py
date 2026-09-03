"""Faz 1 — Sub-Agent Icerik Motoru: pipeline iskeleti.

01-faz1-sub-agent-icerik-motoru.md §3 (roller) + §7 (sıradaki somut adım:
"sub-agent zincirini `get_disclosure_source()` üzerine inşa etmek").

Bu modul ZINCIRIN ISKELETIDIR:
  * `ingest_new_disclosures()` — GERCEK: kaynagi tarar, yeni bildirimleri
    `content_pipeline_items` tablosuna `pending` olarak yazar, sektoru
    `stock_sectors` tablosundan doldurur, cursor'u `scraper_state`'e yazar.
  * `parse_item()` — GERCEK (deterministik): raw_html → clean_text
    (base64 zaten kaynak adapter'inda cozuldu; burada HTML → duz metin).
  * `analyze_item()` / `write_item()` / `translate_item()` / `review_item()`
    / `publish_item()` — STUB: Analiz/Yazar/Ceviri/Editor/Yayinci agent'lari
    henuz kodlanmadi (kullanicinin Faz 1 kapsami: "veritabani + proje
    taslagi"). Cagrilinca `NotImplementedError` verir.

Orkestrator (APScheduler job'u) daha sonra:
    ingest → parse → analyze → write → translate → review → publish
sirasiyla `status` alanina gore ilerletir.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.config import get_settings
from app.database import async_session
from app.models.content_pipeline_item import (
    STATUS_ANALYZED,
    STATUS_PARSED,
    STATUS_PENDING,
    STATUS_PUBLISHED,
    STATUS_REVIEWED,
    STATUS_WRITTEN,
    ContentPipelineItem,
)
from app.models.scraper_state import ScraperState
from app.models.stock_sector import StockSector
from app.scrapers.disclosure_source import DisclosureRef
from app.scrapers.source_factory import get_disclosure_source

logger = logging.getLogger(__name__)

_CURSOR_KEY = "content_pipeline:last_cursor"


# ────────────────────────────────────────────────────────────
# scraper_state cursor yardimcilari
# ────────────────────────────────────────────────────────────

async def _get_cursor(session) -> Optional[str]:
    row = await session.scalar(
        select(ScraperState).where(ScraperState.key == _CURSOR_KEY)
    )
    return row.value if row else None


async def _set_cursor(session, value: str) -> None:
    row = await session.scalar(
        select(ScraperState).where(ScraperState.key == _CURSOR_KEY)
    )
    if row:
        row.value = value
    else:
        session.add(ScraperState(key=_CURSOR_KEY, value=value))


async def _sector_for(session, stock_code: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """stock_sectors tablosundan (sector_name, sector_index). §6.1.1: KAP sektor vermiyor."""
    if not stock_code:
        return None, None
    row = await session.get(StockSector, stock_code.upper())
    if row:
        return row.sector_name, row.sector_index
    return None, None


# ────────────────────────────────────────────────────────────
# 1) INGEST — Kaynak Tarayici Agent (gercek)
# ────────────────────────────────────────────────────────────

async def ingest_new_disclosures(*, limit: Optional[int] = None) -> int:
    """Yapilandirilmis kaynaktan yeni bildirimleri kuyruga ekler.

    Returns: eklenen yeni satir sayisi.
    """
    settings = get_settings()
    if not settings.CONTENT_ENGINE_ENABLED:
        logger.info("content_pipeline: CONTENT_ENGINE_ENABLED=false — ingest atlandi")
        return 0

    batch = limit or settings.CONTENT_INGEST_BATCH
    added = 0

    async with async_session() as session:
        since = await _get_cursor(session)

        async with get_disclosure_source() as src:
            try:
                refs = await src.list_new(since, limit=batch)
            except Exception as exc:  # noqa: BLE001 — rate limit / ag hatasi
                logger.warning("content_pipeline ingest: kaynak hatasi: %s", exc)
                return 0

            new_cursor = None
            for ref in refs:
                if await _persist_ref(session, ref):
                    added += 1
                if ref.disclosure_index is not None:
                    new_cursor = str(ref.disclosure_index)
                elif ref.published_at:
                    new_cursor = ref.published_at.astimezone(timezone.utc).isoformat()

            if new_cursor is None and since is None:
                # Ilk calistirmada hic bildirim yoksa yine de cursor koy ki
                # bir sonraki tur bastan taramasin.
                try:
                    new_cursor = await src.latest_cursor()
                except Exception:  # noqa: BLE001
                    new_cursor = None

            if new_cursor:
                await _set_cursor(session, new_cursor)

        await session.commit()

    logger.info("content_pipeline ingest: %d yeni bildirim kuyruga eklendi", added)
    return added


async def _persist_ref(session, ref: DisclosureRef) -> bool:
    """Tek bir DisclosureRef'i pending satir olarak yazar. Zaten varsa False."""
    exists = await session.scalar(
        select(ContentPipelineItem.id).where(
            ContentPipelineItem.source == ref.source,
            ContentPipelineItem.source_ref == ref.source_ref,
        )
    )
    if exists:
        return False

    sector_name, sector_index = await _sector_for(session, ref.stock_code)
    session.add(
        ContentPipelineItem(
            source=ref.source,
            source_ref=ref.source_ref,
            disclosure_index=ref.disclosure_index,
            disclosure_class=ref.disclosure_class,
            company_id=ref.company_id,
            stock_code=(ref.stock_code or None) and ref.stock_code.upper(),
            sector_name=sector_name,
            sector_index=sector_index,
            title=ref.title or "",
            kap_url=ref.url,
            published_at=ref.published_at,
            status=STATUS_PENDING,
        )
    )
    return True


# ────────────────────────────────────────────────────────────
# 2) PARSE — Ayristirici Agent (gercek, deterministik)
# ────────────────────────────────────────────────────────────

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t ]+")
_MULTINL_RE = re.compile(r"\n{3,}")


def html_to_text(html: str) -> str:
    """HTML → duz metin. beautifulsoup4 varsa onu, yoksa regex fallback kullanir."""
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup  # projede zaten var (requirements.txt)

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text("\n")
    except Exception:  # noqa: BLE001
        text = _TAG_RE.sub("\n", html)

    text = _WS_RE.sub(" ", text)
    text = _MULTINL_RE.sub("\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


async def fetch_and_parse_item(item_id: int) -> None:
    """pending → parsed: detayı kaynaktan çeker, clean_text üretir."""
    async with async_session() as session:
        item = await session.get(ContentPipelineItem, item_id)
        if not item or item.status != STATUS_PENDING:
            return

        ref = DisclosureRef(
            source_ref=item.source_ref,
            source=item.source,
            title=item.title,
            stock_code=item.stock_code,
            company_id=item.company_id,
            disclosure_index=item.disclosure_index,
            disclosure_class=item.disclosure_class,
            published_at=item.published_at,
            url=item.kap_url,
        )
        item.attempts += 1
        try:
            async with get_disclosure_source(item.source) as src:
                content = await src.fetch_detail(ref)
        except Exception as exc:  # noqa: BLE001
            item.status_detail = f"fetch_detail: {exc}"[:2000]
            await session.commit()
            logger.warning("content_pipeline parse: item=%s hata: %s", item_id, exc)
            return

        item.raw_html = content.raw_html or None
        item.summary = content.summary or item.summary
        item.clean_text = content.clean_text or html_to_text(content.raw_html)
        if content.published_at and not item.published_at:
            item.published_at = content.published_at
        if content.url and not item.kap_url:
            item.kap_url = content.url
        item.status = STATUS_PARSED
        item.status_detail = None
        await session.commit()


# ────────────────────────────────────────────────────────────
# 3+) AI agent asamalari — STUB (henuz kodlanmadi)
# ────────────────────────────────────────────────────────────

_NOT_IMPLEMENTED = (
    "Faz 1 kapsami 'veritabani + proje taslagi' ile sinirli. "
    "Bu agent (01-faz1 §3) sonraki adimda kodlanacak."
)


async def analyze_item(item_id: int) -> None:
    """parsed → analyzed: Analiz/Ozetleyici Agent (§3). clean_text'i
    baglamsallastirir, `analysis_notes` yazar."""
    raise NotImplementedError(f"analyze_item: {_NOT_IMPLEMENTED}")


async def write_item(item_id: int) -> None:
    """analyzed → written: Yazar Agent (§3). Blog formatinda TR taslak uretir,
    `blog_posts` kaydi olusturup `tr_blog_post_id` baglar."""
    raise NotImplementedError(f"write_item: {_NOT_IMPLEMENTED}")


async def translate_item(item_id: int) -> None:
    """Ceviri/Lokalizasyon Agent (§6.2). TR taslaktan EN uretir,
    `en_blog_post_id` baglar."""
    raise NotImplementedError(f"translate_item: {_NOT_IMPLEMENTED}")


async def review_item(item_id: int) -> None:
    """written → reviewed | rejected: Editor/Kalite Kontrol Agent (§3, §6.5).
    Sayisal verileri kaynakla capraz kontrol eder, halusinasyonu eler."""
    raise NotImplementedError(f"review_item: {_NOT_IMPLEMENTED}")


async def publish_item(item_id: int) -> None:
    """reviewed → published: Yayinci Agent (§3). blog_posts.is_published=true,
    published_at_pipeline set."""
    raise NotImplementedError(f"publish_item: {_NOT_IMPLEMENTED}")


# ────────────────────────────────────────────────────────────
# Orkestrator giris noktasi (iskelet)
# ────────────────────────────────────────────────────────────

_NEXT_STAGE = {
    STATUS_PENDING: fetch_and_parse_item,
    STATUS_PARSED: analyze_item,
    STATUS_ANALYZED: write_item,
    STATUS_WRITTEN: review_item,
    STATUS_REVIEWED: publish_item,
}


async def run_pipeline_once(*, max_items: int = 10) -> dict[str, int]:
    """Kuyrukta ilerlemeye hazir satirlari bir adim ilerletir.

    Faz 1 iskeleti: sadece ingest + parse GERCEK calisir; ilerisi
    NotImplementedError verir (yakalanip sayaca yazilir).
    """
    counts: dict[str, int] = {}
    await ingest_new_disclosures()

    async with async_session() as session:
        rows = (
            await session.scalars(
                select(ContentPipelineItem)
                .where(ContentPipelineItem.status.in_(list(_NEXT_STAGE.keys())))
                .order_by(ContentPipelineItem.published_at.asc().nulls_last())
                .limit(max_items)
            )
        ).all()
        item_ids = [(r.id, r.status) for r in rows]

    for item_id, status in item_ids:
        stage = _NEXT_STAGE.get(status)
        if not stage:
            continue
        try:
            await stage(item_id)
            counts[status] = counts.get(status, 0) + 1
        except NotImplementedError as exc:
            logger.debug("content_pipeline: %s", exc)
            counts.setdefault(f"skipped:{status}", 0)
            counts[f"skipped:{status}"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("content_pipeline stage %s (item=%s) hata: %s", status, item_id, exc)

    return counts
