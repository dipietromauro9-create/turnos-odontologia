"""Parámetros compartidos de los endpoints de agenda."""

import uuid
from typing import Annotated

from fastapi import Query

ProfesionalFiltro = Annotated[uuid.UUID | None, Query()]
