"""content_pipeline_items — Faz 1 sub-agent icerik motoru is kuyrugu

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
Create Date: 2026-09-03

01-faz1-sub-agent-icerik-motoru.md §7 DB taslagi. Her satir tek bir KAP
bildiriminin sub-agent zincirindeki durumunu tutar
(pending → parsed → analyzed → written → reviewed → published / rejected / failed).

NOT: app/database.py init_db() icinde ayni tablo idempotent CREATE TABLE
IF NOT EXISTS ile de olusturuluyor (projedeki mevcut kalip). Bu migration
alembic gecmisini butun tutmak icin var.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


revision: str = 'h8c9d0e1f2a3'
down_revision: Union[str, None] = 'g7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_pipeline_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=False),
        sa.Column("disclosure_index", sa.BigInteger(), nullable=True),
        sa.Column("disclosure_class", sa.String(length=8), nullable=True),
        sa.Column("company_id", sa.String(length=32), nullable=True),
        sa.Column("stock_code", sa.String(length=16), nullable=True),
        sa.Column("sector_name", sa.String(length=80), nullable=True),
        sa.Column("sector_index", sa.String(length=10), nullable=True),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("kap_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("clean_text", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("analysis_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("status_detail", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tr_blog_post_id", sa.Integer(), nullable=True),
        sa.Column("en_blog_post_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("published_at_pipeline", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("source", "source_ref", name="uq_content_pipeline_source_ref"),
    )
    op.create_index("idx_content_pipeline_status", "content_pipeline_items", ["status"])
    op.create_index("idx_content_pipeline_stock", "content_pipeline_items", ["stock_code"])
    op.create_index("idx_content_pipeline_published", "content_pipeline_items", ["published_at"])


def downgrade() -> None:
    op.drop_index("idx_content_pipeline_published", table_name="content_pipeline_items")
    op.drop_index("idx_content_pipeline_stock", table_name="content_pipeline_items")
    op.drop_index("idx_content_pipeline_status", table_name="content_pipeline_items")
    op.drop_table("content_pipeline_items")
