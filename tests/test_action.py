from dwim.action import build_prompt, parse_response, run_action


def test_build_prompt_includes_intent_and_context():
    p = build_prompt("find big files", {"cwd": "/tmp/x", "git": "main"})
    assert "find big files" in p
    assert "/tmp/x" in p


def test_parse_valid_json():
    out = parse_response('{"answer": "ok", "commands": ["ls -la", "du -sh *"]}')
    assert out["answer"] == "ok"
    assert [c["cmd"] for c in out["commands"]] == ["ls -la", "du -sh *"]


def test_parse_json_embedded_in_prose():
    raw = 'Here you go:\n{"answer":"hi","commands":["pwd"]}\nHope that helps.'
    out = parse_response(raw)
    assert [c["cmd"] for c in out["commands"]] == ["pwd"]


def test_parse_malformed_falls_back_to_answer():
    out = parse_response("just some text, no json")
    assert out["commands"] == []
    assert "just some text" in out["answer"]


def test_run_action_uses_injected_runner():
    captured = {}

    def fake_runner(prompt, model):
        captured["prompt"] = prompt
        return '{"answer":"found","commands":["du -sh *"]}', "sess-0"

    out = run_action("what is big", runner=fake_runner,
                     context={"cwd": "/tmp", "git": ""})
    assert [c["cmd"] for c in out["commands"]] == ["du -sh *"]
    assert "what is big" in captured["prompt"]


def test_parse_json_after_prose_with_earlier_brace():
    raw = ('While investigating I saw a config like {"foo": "bar"} in the repo. '
           'Here is my answer: {"answer": "use rg", "commands": ["rg TODO"]}')
    out = parse_response(raw)
    assert out["answer"] == "use rg"
    assert [c["cmd"] for c in out["commands"]] == ["rg TODO"]


def test_parse_non_list_commands_falls_back():
    out = parse_response('{"answer": "do this", "commands": "ls -la"}')
    assert out["commands"] == []          # not char-split
    assert "do this" in out["answer"]


def test_parse_brace_inside_json_string_value():
    out = parse_response('{"answer": "run {rg}", "commands": ["rg x"]}')
    assert [c["cmd"] for c in out["commands"]] == ["rg x"]  # brace inside a string value must not confuse the scanner


def test_run_action_passes_model_through():
    seen = {}
    def fake_runner(prompt, model):
        seen["model"] = model
        return '{"answer":"ok","commands":["pwd"]}', "sess-1"
    run_action("hi", runner=fake_runner, context={"cwd": "/tmp"}, model="sonnet")
    assert seen["model"] == "sonnet"


def test_run_action_surfaces_session_id():
    from dwim.action import run_action
    # runner now returns (text, session_id); text is the model's raw output.
    runner = lambda prompt, model: ('{"answer":"hi","commands":[]}', "sess-7")
    out = run_action("x", runner=runner, context={"cwd": "/c"})
    assert out["answer"] == "hi" and out["session_id"] == "sess-7"


def test_parse_command_objects_carry_desc():
    out = parse_response('{"answer":"", "commands":[{"cmd":"ls -la","desc":"list files"}]}')
    assert out["commands"] == [{"cmd": "ls -la", "desc": "list files"}]


def test_parse_bare_string_commands_get_empty_desc():
    out = parse_response('{"answer":"", "commands":["pwd"]}')
    assert out["commands"] == [{"cmd": "pwd", "desc": ""}]


def test_prompt_mentions_locate_and_reach():
    from dwim.action import build_prompt
    p = build_prompt("why is x big", {"cwd": "/c", "roots": "~/Documents, ~",
                                       "inventory": "helixa 2.0G"})
    assert "dwim-locate" in p
    assert "~/Documents" in p           # spatial root guidance present
    assert "helixa 2.0G" in p           # inventory injected
    low = p.lower()
    assert "reproduce" in low            # top command must reproduce the finding


def test_prompt_reach_guidance_is_in_system_prompt():
    from dwim.action import SYSTEM_PROMPT
    assert "dwim-locate" in SYSTEM_PROMPT
    assert "Glob" in SYSTEM_PROMPT       # explains Glob/Grep are cwd-only


def test_prompt_mentions_dwim_git_for_other_repos():
    from dwim.action import SYSTEM_PROMPT
    assert "dwim-git" in SYSTEM_PROMPT


def test_system_prompt_has_destructive_enumeration_clause():
    from dwim.action import SYSTEM_PROMPT
    p = SYSTEM_PROMPT.lower()
    # tells the agent to discover read-only itself and offer several ordered options
    assert "remediation option" in p
    assert "safest" in p
    assert "do not return the discovery" in p


def test_run_action_forwards_multiple_commands():
    from dwim.action import run_action

    def fake_runner(prompt, model):
        return ('{"answer":"17 worktrees, 3 merged","commands":['
                '{"cmd":"git worktree prune","desc":"clear stale worktrees"},'
                '{"cmd":"git worktree remove a b c","desc":"remove 3 merged"}]}',
                "sid-1")

    out = run_action("delete the unrelated worktrees", runner=fake_runner,
                     context={"cwd": "/x"}, model="haiku")
    assert [c["cmd"] for c in out["commands"]] == \
        ["git worktree prune", "git worktree remove a b c"]
    assert out["session_id"] == "sid-1"
