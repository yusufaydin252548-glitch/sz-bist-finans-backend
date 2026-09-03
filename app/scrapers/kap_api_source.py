"""Yol B — resmi KAP/MKK API'si uzerinden bildirim kaynagi.

`KAPApiClient` (app/scrapers/kap_api_client.py) uzerine ince bir adapter;
`DisclosureSource` arayuzunu uygular. 01-faz1 §2 Yol B akisi:

    lastDisclosureIndex -> disclosures -> disclosureDetail -> decode & parse

Rate limit: ucretsiz plan 6 istek/dk (production sozlesmesiyle 1.000/dk).
`list_new()` bu yuzden `limit` ile sinirli calisir; cagiran taraf
`KAPThrottled` yakalayip beklemelidir.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.scrapers.disclosure_source import (
    DisclosureContent,
    DisclosureRef,
    DisclosureSource,
)
from app.scrapers.kap_api_client import KAPApiClient, decode_html_message

logger = logging.getLogger(__name__)

# list_new(since=None) ilk calistirmada kac index geriye baksin.
_COLD_START_LOOKBACK = 30


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(str(value)[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


class KAPApiSource(DisclosureSource):
    """DisclosureSource implementasyonu — resmi KAP API (Yol B)."""

    name = "kap_api"

    def __init__(self, client: Optional[KAPApiClient] = None):
        self._client = client or KAPApiClient()
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.close()

    # -- kesif --------------------------------------------------------------

    async def latest_cursor(self) -> str:
        return str(await self._client.last_disclosure_index())

    async def list_new(
        self, since: Optional[str], *, limit: int = 50
    ) -> list[DisclosureRef]:
        latest = await self._client.last_disclosure_index()

        if since is None:
            start = max(1, latest - _COLD_START_LOOKBACK + 1)
        else:
            start = int(since) + 1

        if start > latest:
            return []

        indices = range(start, min(latest, start + limit - 1) + 1)
        refs: list[DisclosureRef] = []
        for idx in indices:
            row = await self._client.disclosure(idx)
            if not row:
                continue
            refs.append(self._row_to_ref(idx, row))
        logger.info(
            "KAPApiSource.list_new: %d yeni bildirim (%d..%d, latest=%d)",
            len(refs), start, indices[-1] if refs else start, latest,
        )
        return refs

    async def fetch_detail(self, ref: DisclosureRef) -> DisclosureContent:
        file_types = ref.extra.get("acceptedDataFileTypes") or ["html"]
        file_type = "html" if "html" in file_types else file_types[0]

        idx = ref.disclosure_index or ref.source_ref
        detail = await self._client.disclosure_detail(idx, file_type=file_type)

        subject = detail.get("subject") or {}
        summary_obj = detail.get("summary") or {}
        summary = summary_obj.get("tr") or summary_obj.get("en") or ""

        raw_html = ""
        for msg in detail.get("htmlMessages") or []:
            payload = msg.get("tr") or msg.get("en")
            if payload:
                try:
                    raw_html += decode_html_message(payload)
                except Exception as exc:  # noqa: BLE001 — kaynak veri bozuk olabilir
                    logger.warning("htmlMessages decode hatasi (idx=%s): %s", idx, exc)

        return DisclosureContent(
            ref=ref,
            summary=summary or subject.get("tr") or ref.title,
            raw_html=raw_html,
            published_at=_parse_dt(detail.get("time")) or ref.published_at,
            url=detail.get("link") or ref.url,
            attachments=list(detail.get("attachmentUrls") or []),
            extra={"subject": subject, "relatedStocks": detail.get("relatedStocks")},
        )

    # -- ic yardimcilar --------------------------------------------------

    @staticmethod
    def _row_to_ref(idx: int, row: dict) -> DisclosureRef:
        stock = row.get("stockCode") or row.get("relatedStocks")
        if isinstance(stock, list):
            stock = stock[0] if stock else None
        return DisclosureRef(
            source_ref=str(idx),
            source="kap_api",
            title=(row.get("title") or "").strip(),
            stock_code=(stock or None) and str(stock).split(",")[0].strip() or None,
            company_id=str(row["companyId"]) if row.get("companyId") is not None else None,
            disclosure_index=idx,
            disclosure_class=row.get("disclosureClass") or row.get("disclosureType"),
            url=row.get("link"),
            extra={
                "subReportIds": row.get("subReportIds"),
                "acceptedDataFileTypes": row.get("acceptedDataFileTypes"),
            },
        )
