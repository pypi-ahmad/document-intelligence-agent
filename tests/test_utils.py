from utils import chunk_page_text, new_id, safe_json_loads, truncate


def test_safe_json_loads_valid():
    assert safe_json_loads('{"a": 1}') == {"a": 1}


def test_safe_json_loads_fenced():
    assert safe_json_loads('```json\n{"a": 1}\n```') == {"a": 1}
    assert safe_json_loads('```\n{"a": 1}\n```') == {"a": 1}


def test_safe_json_loads_prose_around_json():
    assert safe_json_loads('Sure, here it is: {"a": 1} - hope that helps!') == {"a": 1}


def test_safe_json_loads_malformed_returns_none():
    assert safe_json_loads("not json at all") is None


def test_chunk_page_text_splits_multiple_paragraphs():
    text = "First paragraph with some words.\n\nSecond paragraph with more words here."
    chunks = chunk_page_text(text)
    assert len(chunks) >= 1
    assert all(c.strip() for c in chunks)


def test_chunk_page_text_empty_returns_empty_list():
    assert chunk_page_text("") == []
    assert chunk_page_text("   ") == []


def test_truncate_short_text_unchanged():
    assert truncate("short text", 100) == "short text"


def test_truncate_long_text_gets_ellipsis():
    long_text = "word " * 50
    result = truncate(long_text, 20)
    assert len(result) <= 21
    assert result.endswith("…")


def test_new_id_has_prefix():
    generated = new_id("doc")
    assert generated.startswith("doc_")
    assert len(generated) > len("doc_")
