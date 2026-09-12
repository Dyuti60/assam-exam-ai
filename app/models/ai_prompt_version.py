from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ai_execution_run import AiExecutionRun


class AiPromptVersion(Base):
    __tablename__ = "ai_prompt_versions"
    __table_args__ = (
        CheckConstraint(
            "prompt_key ~ '^[a-z][a-z0-9_.-]*$' AND char_length(prompt_key) <= 100",
            name="ck_ai_prompt_versions_prompt_key",
        ),
        CheckConstraint("version > 0", name="ck_ai_prompt_versions_version_positive"),
        CheckConstraint(
            "btrim(system_template) <> '' AND char_length(system_template) <= 20000",
            name="ck_ai_prompt_versions_system_template",
        ),
        CheckConstraint(
            "btrim(user_template) <> '' AND char_length(user_template) <= 20000",
            name="ck_ai_prompt_versions_user_template",
        ),
        CheckConstraint(
            "input_schema_key ~ '^[a-z][a-z0-9_.-]*$' "
            "AND char_length(input_schema_key) <= 100",
            name="ck_ai_prompt_versions_input_schema_key",
        ),
        CheckConstraint(
            "output_schema_key ~ '^[a-z][a-z0-9_.-]*$' "
            "AND char_length(output_schema_key) <= 100",
            name="ck_ai_prompt_versions_output_schema_key",
        ),
        CheckConstraint(
            "input_schema_version > 0 AND output_schema_version > 0",
            name="ck_ai_prompt_versions_schema_versions_positive",
        ),
        CheckConstraint(
            "checksum ~ '^[0-9a-f]{64}$'",
            name="ck_ai_prompt_versions_checksum",
        ),
        UniqueConstraint("prompt_key", "version", name="uq_ai_prompt_versions_key_version"),
        UniqueConstraint(
            "id",
            "prompt_key",
            "version",
            "checksum",
            name="uq_ai_prompt_versions_identity_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    system_template: Mapped[str] = mapped_column(Text, nullable=False)
    user_template: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema_key: Mapped[str] = mapped_column(String(100), nullable=False)
    input_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    output_schema_key: Mapped[str] = mapped_column(String(100), nullable=False)
    output_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    executions: Mapped[list["AiExecutionRun"]] = relationship(
        back_populates="prompt_version_record",
        foreign_keys=(
            "[AiExecutionRun.ai_prompt_version_id, AiExecutionRun.prompt_key, "
            "AiExecutionRun.prompt_version, AiExecutionRun.prompt_checksum]"
        ),
    )
