from __future__ import annotations

from collections.abc import Sequence
import json

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator, UserDefinedType


class VectorComparator(UserDefinedType.Comparator):
    def cosine_distance(self, other):
        return self.expr.op("<=>")(other)


class PGVector(UserDefinedType):
    cache_ok = True
    comparator_factory = VectorComparator

    def __init__(self, dimensions: int | None = None) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **kw) -> str:
        if self.dimensions:
            return f"vector({self.dimensions})"
        return "vector"

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            return [float(item) for item in value]

        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            if isinstance(value, str):
                stripped = value.strip().replace("{", "[").replace("}", "]")
                try:
                    return [float(item) for item in json.loads(stripped)]
                except Exception:
                    return [float(item) for item in stripped.strip("[]").split(",") if item]
            return [float(item) for item in value]

        return process


class EmbeddingVector(TypeDecorator):
    """Store pgvector vectors on Postgres and JSON arrays elsewhere."""

    impl = JSON
    cache_ok = True
    comparator_factory = VectorComparator

    def __init__(self, dimensions: int | None = None) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGVector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Sequence[float] | None, dialect):
        if value is None:
            return None
        return [float(item) for item in value]

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return [float(item) for item in value]
