from types import SimpleNamespace

from app.models.vector import EmbeddingVector, PGVector, _format_vector_literal


def test_vector_literal_and_pgvector_processors():
    assert _format_vector_literal([1, 2.5]) == "[1.0,2.5]"

    vector = PGVector(3)
    assert vector.get_col_spec() == "vector(3)"
    assert PGVector().get_col_spec() == "vector"

    bind = vector.bind_processor(None)
    assert bind([1, 2]) == "[1.0,2.0]"
    assert bind("raw") == "raw"
    assert bind(None) is None

    result = vector.result_processor(None, None)
    assert result("[1,2.5]") == [1.0, 2.5]
    assert result("{1,2.5}") == [1.0, 2.5]
    assert result([1, 2.5]) == [1.0, 2.5]
    assert result(None) is None


def test_embedding_vector_uses_json_or_pgvector_by_dialect():
    embedding = EmbeddingVector(2)
    postgres = SimpleNamespace(name="postgresql", type_descriptor=lambda value: value)
    sqlite = SimpleNamespace(name="sqlite", type_descriptor=lambda value: value)

    assert embedding.load_dialect_impl(postgres).__class__.__name__ == "PGVector"
    assert embedding.load_dialect_impl(sqlite).__class__.__name__ == "JSON"
    assert embedding.process_bind_param([1, 2], postgres) == "[1.0,2.0]"
    assert embedding.process_bind_param([1, 2], sqlite) == [1.0, 2.0]
    assert embedding.process_bind_param(None, sqlite) is None
    assert embedding.process_result_value([1, 2], sqlite) == [1.0, 2.0]
    assert embedding.process_result_value(None, sqlite) is None
