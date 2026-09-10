from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class ModelResponse:
    provider: str; status: str; content: Any; stdout: str=""; stderr: str=""; usage_type: str="UNAVAILABLE"

class ModelAdapter(ABC):
    @abstractmethod
    def health_check(self) -> dict: ...
    @abstractmethod
    def execute(self, prompt: str, output_schema: dict | None=None) -> ModelResponse: ...

class CodexCliAdapter(ModelAdapter):
    def health_check(self): return {"provider":"codex_cli","capability":"CLI generation and structured output","credentials_stored":False}
    def execute(self, prompt, output_schema=None): raise RuntimeError("Codex CLI execution is disabled until local authentication is verified")

class CopilotAdapter(ModelAdapter):
    def health_check(self): return {"provider":"copilot","capability":"gh copilot capability probe","credentials_stored":False}
    def execute(self, prompt, output_schema=None): raise RuntimeError("Copilot execution requires the corporate GitHub CLI session and policy approval")
