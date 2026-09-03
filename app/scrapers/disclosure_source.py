"""Bildirim kaynagi ortak arayuzu — Faz 1 sub-agent icerik motoru.

01-faz1-sub-agent-icerik-motoru.md §3 ve §7:
    "Kaynak Tarayici ve Detay Cekici agent'larinin veri kaynagi soyutlanmis
     olmali (... hem BorsapySource hem KAPApiSource implementasyonu) — boylece
     Yol A'dan Yol B'ye gecis, sadece bir konfigurasyon degisikligi olur."

Iki somut implementasyon:
    - `BorsapySource`  (Yol A / MVP)      → app/scrapers/borsapy_source.py
    - `KAPApiSource`   (Yol B / resmi API) → app/scrapers/kap_api_source.py

Kaynak secimi: `app/scrapers/source_factory.get_disclosure_source()` —
`settings.CONTENT_DATA_SOURCE` degerine gore.

Sub-agent zinciri (Analiz/Yazar/Editor/Yayinci) bu arayuzun uzerine
`app/services/content_pipeline.py` icinde kurulur.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class DisclosureRef:
    """Bir bildirimin ozet/kimlik kaydi — "Kaynak Tarayici Agent" ciktisi.

    Yol B'de `disclosures` servisinin, Yol A'da `Ticker.news` satirinin
    kaynaktan bagimsiz karsiligi. `fetch_detail()` icin gereken referans.
    """

    # Kaynakta bu bildirimi tekil olarak isaret eden deger.
    # Yol B: disclosureIndex (str). Yol A: haber URL'si / id.
    source_ref: str
    source: str                              # "borsapy" | "kap_api"

    title: str = ""
    stock_code: Optional[str] = None         # BIST hisse kodu (sektor eslemesi icin)
    company_id: Optional[str] = None         # Yol B companyId / Yol A bos olabilir
    disclosure_index: Optional[int] = None   # Yol B; Yol A'da None
    disclosure_class: Optional[str] = None   # FR | ODA | DG | DUY | FON | CA
    published_at: Optional[datetime] = None
    url: Optional[str] = None                # orijinal KAP/haber linki
    # Detay cekimi icin kaynaga geri verilecek ham alanlar (subReportIds vb.)
    extra: dict = field(default_factory=dict)


@dataclass(slots=True)
class DisclosureContent:
    """Bir bildirimin tam icerigi — "Detay Cekici" + "Ayristirici" ciktisi.

    `raw_html`: kaynaktan gelen ham HTML (Yol B'de base64 cozulmus hali).
    `clean_text`: HTML'den cikarilmis duz metin (LLM'e verilecek girdi).
    Ayristirma `app/services/content_pipeline.parse_item()` icinde yapilir;
    kaynak sadece `raw_html`/`summary` doldurmakla yukumludur.
    """

    ref: DisclosureRef
    summary: str = ""                        # kisa ozet (varsa) — blog girisi malzemesi
    raw_html: str = ""
    clean_text: str = ""
    published_at: Optional[datetime] = None
    url: Optional[str] = None
    attachments: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


class DisclosureSource(abc.ABC):
    """Yol A / Yol B ortak arayuzu.

    Orkestrator bu arayuz uzerinden calisir; hangi implementasyonun
    baglandigini bilmez.
    """

    name: str = "base"

    # -- kesif --------------------------------------------------------------

    @abc.abstractmethod
    async def latest_cursor(self) -> str:
        """Su anki en guncel bildirim isaretcisi (artimli senkron ust siniri).

        Yol B: `lastDisclosureIndex` (str). Yol A: ISO tarih damgasi.
        `ScraperState` icinde saklanip bir sonraki `list_new()` cagrisina
        `since` olarak verilir.
        """

    @abc.abstractmethod
    async def list_new(self, since: Optional[str], *, limit: int = 50) -> list[DisclosureRef]:
        """`since` isaretcisinden sonraki yeni bildirimler (eskiden yeniye).

        `since` None ise kaynak makul bir baslangic penceresi secer
        (ilk calistirma). `limit` rate-limit dostu bir ust sinirdir.
        """

    @abc.abstractmethod
    async def fetch_detail(self, ref: DisclosureRef) -> DisclosureContent:
        """Tek bir bildirimin tam icerigini getirir."""

    # -- yasam dongusu ----------------------------------------------------

    async def aclose(self) -> None:
        """Alt kaynaklari kapatir (HTTP client vb.). Varsayilan: no-op."""

    async def __aenter__(self) -> "DisclosureSource":
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.aclose()
