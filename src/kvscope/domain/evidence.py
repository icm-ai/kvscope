"""Evidence and confidence domain objects."""

from datetime import datetime
from typing import Annotated

from pydantic import Field, StrictStr

from kvscope.domain.base import DomainModel


class Evidence(DomainModel):
    """A traceable source supporting a profile value or estimate."""

    evidence_id: Annotated[StrictStr, Field(min_length=1)]
    source_type: Annotated[StrictStr, Field(min_length=1)]
    source: Annotated[StrictStr, Field(min_length=1)]
    version: StrictStr | None = None
    observed_at: datetime | None = None
    notes: StrictStr | None = None
