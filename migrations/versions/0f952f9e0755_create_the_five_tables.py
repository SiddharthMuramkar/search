"""create the five tables

Revision ID: 0f952f9e0755
Revises:
Create Date: 2026-10-13 11:01:09.807590

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0f952f9e0755"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "comparisons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("winner_run_id", sa.Uuid(), nullable=True),
        sa.Column("method", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("architecture", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("report", sa.String(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("trace_id", sa.String(), nullable=True),
        sa.Column("comparison_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["comparison_id"], ["comparisons.id"], name="fk_runs_comparison_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # runs and comparisons refer to each other, so this key is added after both tables exist.
    # Autogenerate wrote it inside create_table("comparisons") with use_alter=True, and
    # create_table leaves such a key out: the key was never created.
    op.create_foreign_key(
        "fk_comparisons_winner_run_id", "comparisons", "runs", ["winner_run_id"], ["id"]
    )
    op.create_table(
        "evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("comparison_id", sa.Uuid(), nullable=False),
        sa.Column("scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("judge_model", sa.String(), nullable=False),
        sa.Column("rubric_version", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparison_id"], ["comparisons.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("span_id", sa.String(), nullable=False),
        sa.Column("parent_span_id", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=False),
        sa.Column("n", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("snippet", sa.String(), nullable=True),
        sa.Column("cited", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.ForeignKeyConstraint(["step_id"], ["steps.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "url"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # first the key of the cycle: with it, runs cannot be dropped before comparisons
    op.drop_constraint("fk_comparisons_winner_run_id", "comparisons", type_="foreignkey")
    op.drop_table("sources")
    op.drop_table("steps")
    op.drop_table("evaluations")
    op.drop_table("runs")
    op.drop_table("comparisons")
