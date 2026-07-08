from dwim.classify import classify

def test_imperatives_are_tasks():
    for t in ["fix the failing test", "add a --json flag", "make the test pass",
              "rename foo to bar everywhere", "bump the version to 0.4",
              "refactor search.py", "delete the dead code", "create a config file"]:
        assert classify(t) == "task", t

def test_interrogatives_are_questions():
    for q in ["how does the index work?", "what is dwim-rag", "why is this slow",
              "where did I add the pin", "does the loop confine writes",
              "is the classifier deterministic"]:
        assert classify(q) == "question", q

def test_ambiguous_defaults_to_question():
    # Safe default: a wrong guess only costs one keystroke, and question is the
    # non-mutating path.
    assert classify("") == "question"
    assert classify("the rag index") == "question"
    assert classify("dwim") == "question"

def test_leading_whitespace_and_case_insensitive():
    assert classify("   Fix the bug") == "task"
    assert classify("HOW does it work") == "question"
