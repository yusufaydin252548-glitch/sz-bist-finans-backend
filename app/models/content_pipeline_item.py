"""Icerik motoru is kuyrugu — bir bildirimin sub-agent zincirindeki durumu.

01-faz1-sub-agent-icerik-motoru.md §3 (roller) + §7 (DB taslagi).

Her satir tek bir KAP bildirimini temsil eder ve zincirin neresinde
oldugunu (`status`) tutar:

    pending → parsed → analyzed → written → reviewed → published
                                         └→ rejected   (Editor Agent reddi)
    (herhangi bir asamada hata) → failed

Yayinlanan ciktilar `blog_posts` tablosuna yazilir; buradaki
`tr_blog_post_id` / `en_blog_post_id` o kayitlara isaret eder (gevsek
baglama — FK degil, projedeki diger modellerle tutarli).
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base

# status akisi — tek yerde tanimli, pipeline bu sabitleri kullanir.
STATUS_PENDING = "pending"
STATUS_PARSED = "parsed"
STATUS_ANALYZED = "analyzed"
STATUS_WRITTEN = "written"
STATUS_REVIEWED = "reviewed"
STATUS_PUBLISHED = "published"
STATUS_REJECTED = "rejected"
STATUS_FAILED = "failed"

STATUS_FLOW = [
    STATUS_PENDING,
    STATUS_PARSED,
    STATUS_ANALYZED,
    STATUS_WRITTEN,
    STATUS_REVIEWED,
    STATUS_PUBLISHED,
]


class ContentPipelineItem(Base):
    """Sub-agent icerik zincirinde tek bir bildirimin is kaydi."""

    __tablename__ = "content_pipeline_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    # -- kaynak kimligi (Yol A / Yol B) --
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="borsapy | kap_api"
    )
    source_ref: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Kaynakta bildirimi tekil isaret eden deger"
    )
    disclosure_index: Mapped[int | None] = mapped_column(
        BigInteger, comment="Yol B disclosureIndex (Yol A'da NULL)"
    )
    disclosure_class: Mapped[str | None] = mapped_column(
        String(8), comment="FR | ODA | DG | DUY | FON | CA"
    )

    # -- sirket / sektor (§6.1.1: sektor KAP'ta yok, borsapy/StockSector'dan) --
    company_id: Mapped[str | None] = mapped_column(String(32))
    stock_code: Mapped[str | None] = mapped_column(String(16), comment="BIST hisse kodu")
    sector_name: Mapped[str | None] = mapped_column(String(80))
    sector_index: Mapped[str | None] = mapped_column(String(10), comment="Ornek: XBANK")

    # -- icerik --
    title: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    kap_url: Mapped[str | None] = mapped_column(Text, comment="Orijinal KAP/haber linki")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_html: Mapped[str | None] = mapped_column(Text, comment="Ham HTML (base64 cozulmus)")
    clean_text: Mapped[str | None] = mapped_column(Text, comment="Ayristirici ciktisi — duz metin")
    summary: Mapped[str | None] = mapped_column(Text, comment="Kaynak ozeti")
    analysis_notes: Mapped[str | None] = mapped_column(Text, comment="Analiz/Ozetleyici Agent ciktisi")

    # -- durum --
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=STATUS_PENDING, server_default=STATUS_PENDING
    )
    status_detail: Mapped[str | None] = mapped_column(
        Text, comment="Hata mesaji / Editor red gerekcesi"
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # -- ciktilar (blog_posts.id — gevsek baglama) --
    tr_blog_post_id: Mapped[int | None] = mapped_column(Integer)
    en_blog_post_id: Mapped[int | None] = mapped_column(Integer)

    # -- zaman damgalari --
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    published_at_pipeline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Zincirin sonunda yayin zamani"
    )

    __table_args__ = (
        UniqueConstraint("source", "source_ref", name="uq_content_pipeline_source_ref"),
        Index("idx_content_pipeline_status", "status"),
        Index("idx_content_pipeline_stock", "stock_code"),
        Index("idx_content_pipeline_published", "published_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ContentPipelineItem(id={self.id}, source={self.source}, "
            f"ref={self.source_ref}, status={self.status})>"
        )
