from dwim.rag.chunker import chunk_text

def test_chunks_cover_lines_with_overlap():
    text = "\n".join(f"line{i}" for i in range(1, 101))   # 100 lines
    cs = chunk_text(text)
    assert cs[0]["start"] == 1
    assert cs[0]["end"] == 40                              # window 40
    assert cs[1]["start"] == 31                            # overlap 10 -> step 30
    assert cs[-1]["end"] == 100                            # last line covered
    for c in cs:
        assert c["text"] and c["start"] <= c["end"]

def test_empty_and_blank():
    assert chunk_text("") == []
    assert chunk_text("\n\n\n") == []
