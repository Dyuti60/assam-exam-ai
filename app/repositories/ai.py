from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AiExecutionRun, AiPromptVersion


class AiRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_prompt_version(self, prompt: AiPromptVersion) -> AiPromptVersion:
        self.session.add(prompt)
        self.session.flush()
        return prompt

    def get_prompt_version(self, prompt_id: int) -> AiPromptVersion | None:
        with self.session.no_autoflush:
            return self.session.scalar(
                select(AiPromptVersion).where(AiPromptVersion.id == prompt_id)
            )

    def get_prompt_version_exact(
        self, prompt_id: int, prompt_key: str, version: int, checksum: str
    ) -> AiPromptVersion | None:
        with self.session.no_autoflush:
            return self.session.scalar(
                select(AiPromptVersion).where(
                    AiPromptVersion.id == prompt_id,
                    AiPromptVersion.prompt_key == prompt_key,
                    AiPromptVersion.version == version,
                    AiPromptVersion.checksum == checksum,
                )
            )

    def add_execution(self, execution: AiExecutionRun) -> AiExecutionRun:
        self.session.add(execution)
        self.session.flush()
        return execution

    def get_execution(self, execution_id: int) -> AiExecutionRun | None:
        with self.session.no_autoflush:
            return self.session.scalar(
                select(AiExecutionRun).where(AiExecutionRun.id == execution_id)
            )
