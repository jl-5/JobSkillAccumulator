from abc import ABC, abstractmethod
from typing import Callable

from app.models import JobPosting

ProgressCallback = Callable[[dict], None]


class JobProvider(ABC):
    name: str

    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    def fetch(
        self,
        query: str,
        limit: int,
        country: str,
        site_result_cap: int | None = None,
        exclude_defense: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> list[JobPosting]:
        ...
