"""add provider-neutral AI prompt and execution audit foundation

Revision ID: c9f2a6d4e817
Revises: b8f4e1c7d526
Create Date: 2026-09-12

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9f2a6d4e817"
down_revision: str | Sequence[str] | None = "b8f4e1c7d526"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_prompt_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prompt_key", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("system_template", sa.Text(), nullable=False),
        sa.Column("user_template", sa.Text(), nullable=False),
        sa.Column("input_schema_key", sa.String(length=100), nullable=False),
        sa.Column("input_schema_version", sa.Integer(), nullable=False),
        sa.Column("output_schema_key", sa.String(length=100), nullable=False),
        sa.Column("output_schema_version", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "prompt_key ~ '^[a-z][a-z0-9_.-]*$' AND char_length(prompt_key) <= 100",
            name="ck_ai_prompt_versions_prompt_key",
        ),
        sa.CheckConstraint("version > 0", name="ck_ai_prompt_versions_version_positive"),
        sa.CheckConstraint(
            "btrim(system_template) <> '' AND char_length(system_template) <= 20000",
            name="ck_ai_prompt_versions_system_template",
        ),
        sa.CheckConstraint(
            "btrim(user_template) <> '' AND char_length(user_template) <= 20000",
            name="ck_ai_prompt_versions_user_template",
        ),
        sa.CheckConstraint(
            "input_schema_key ~ '^[a-z][a-z0-9_.-]*$' "
            "AND char_length(input_schema_key) <= 100",
            name="ck_ai_prompt_versions_input_schema_key",
        ),
        sa.CheckConstraint(
            "output_schema_key ~ '^[a-z][a-z0-9_.-]*$' "
            "AND char_length(output_schema_key) <= 100",
            name="ck_ai_prompt_versions_output_schema_key",
        ),
        sa.CheckConstraint(
            "input_schema_version > 0 AND output_schema_version > 0",
            name="ck_ai_prompt_versions_schema_versions_positive",
        ),
        sa.CheckConstraint(
            "checksum ~ '^[0-9a-f]{64}$'", name="ck_ai_prompt_versions_checksum"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "prompt_key", "version", name="uq_ai_prompt_versions_key_version"
        ),
        sa.UniqueConstraint(
            "id",
            "prompt_key",
            "version",
            "checksum",
            name="uq_ai_prompt_versions_identity_snapshot",
        ),
    )
    op.create_table(
        "ai_execution_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ai_prompt_version_id", sa.Integer(), nullable=False),
        sa.Column("prompt_key", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("prompt_checksum", sa.String(length=64), nullable=False),
        sa.Column("provider_key", sa.String(length=50), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "input_json",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=False,
        ),
        sa.Column("input_sha256", sa.String(length=64), nullable=False),
        sa.Column("rendered_system_sha256", sa.String(length=64), nullable=False),
        sa.Column("rendered_user_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "output_json",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column("output_sha256", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("provider_request_id", sa.String(length=200), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("provider_cost", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("cost_currency", sa.String(length=3), nullable=True),
        sa.Column("finish_reason", sa.String(length=100), nullable=True),
        sa.Column(
            "safety_metadata",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('SUCCEEDED', 'FAILED')", name="ck_ai_execution_runs_status"),
        sa.CheckConstraint(
            "provider_key ~ '^[a-z][a-z0-9_.-]*$' AND char_length(provider_key) <= 50",
            name="ck_ai_execution_runs_provider_key",
        ),
        sa.CheckConstraint(
            "model_id ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]*$' "
            "AND char_length(model_id) <= 128",
            name="ck_ai_execution_runs_model_id",
        ),
        sa.CheckConstraint(
            "char_length(request_id) BETWEEN 1 AND 100 "
            "AND request_id = btrim(request_id) "
            "AND request_id !~ '[[:cntrl:]]' "
            "AND request_id !~ '^[[:space:]]' "
            "AND request_id !~ '[[:space:]]$'",
            name="ck_ai_execution_runs_request_id",
        ),
        sa.CheckConstraint(
            "input_sha256 ~ '^[0-9a-f]{64}$' AND rendered_system_sha256 ~ "
            "'^[0-9a-f]{64}$' AND rendered_user_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_ai_execution_runs_request_hashes",
        ),
        sa.CheckConstraint(
            "output_sha256 IS NULL OR output_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_ai_execution_runs_output_hash",
        ),
        sa.CheckConstraint(
            "error_code IS NULL OR (error_code ~ '^[A-Z][A-Z0-9_]*$' "
            "AND char_length(error_code) <= 100)",
            name="ck_ai_execution_runs_error_code",
        ),
        sa.CheckConstraint(
            "(status = 'SUCCEEDED' AND output_json IS NOT NULL AND output_sha256 "
            "IS NOT NULL AND error_code IS NULL) OR (status = 'FAILED' AND "
            "output_json IS NULL AND output_sha256 IS NULL AND error_code IS NOT NULL)",
            name="ck_ai_execution_runs_terminal_metadata",
        ),
        sa.CheckConstraint(
            "completed_at >= started_at AND duration_ms >= 0",
            name="ck_ai_execution_runs_timing",
        ),
        sa.CheckConstraint(
            "(input_tokens IS NULL OR input_tokens >= 0) AND (output_tokens IS NULL "
            "OR output_tokens >= 0) AND (total_tokens IS NULL OR total_tokens >= 0)",
            name="ck_ai_execution_runs_tokens_non_negative",
        ),
        sa.CheckConstraint(
            "input_tokens IS NULL OR output_tokens IS NULL OR total_tokens IS NULL "
            "OR total_tokens = input_tokens + output_tokens",
            name="ck_ai_execution_runs_token_total",
        ),
        sa.CheckConstraint(
            "(provider_cost IS NULL AND cost_currency IS NULL) OR "
            "(provider_cost IS NOT NULL AND provider_cost >= 0 "
            "AND cost_currency IS NOT NULL AND cost_currency ~ '^[A-Z]{3}$')",
            name="ck_ai_execution_runs_cost_metadata",
        ),
        sa.CheckConstraint(
            "provider_request_id IS NULL OR char_length(provider_request_id) BETWEEN 1 AND 200",
            name="ck_ai_execution_runs_provider_request_id",
        ),
        sa.CheckConstraint(
            "finish_reason IS NULL OR char_length(finish_reason) BETWEEN 1 AND 100",
            name="ck_ai_execution_runs_finish_reason",
        ),
        sa.CheckConstraint(
            "safety_metadata IS NULL OR octet_length(safety_metadata::text) <= 4000",
            name="ck_ai_execution_runs_safety_metadata",
        ),
        sa.ForeignKeyConstraint(
            ["ai_prompt_version_id", "prompt_key", "prompt_version", "prompt_checksum"],
            ["ai_prompt_versions.id", "ai_prompt_versions.prompt_key", "ai_prompt_versions.version", "ai_prompt_versions.checksum"],
            name="fk_ai_execution_runs_prompt_snapshot",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_ai_execution_runs_request_id"),
    )
    op.create_index(
        "ix_ai_execution_runs_prompt_version_id",
        "ai_execution_runs",
        ["ai_prompt_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_execution_runs_prompt_version_id", table_name="ai_execution_runs")
    op.drop_table("ai_execution_runs")
    op.drop_table("ai_prompt_versions")
