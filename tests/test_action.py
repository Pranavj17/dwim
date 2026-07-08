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


def test_parse_rescues_fenced_command_when_no_json():
    # The (esp. deep) model sometimes puts the command in a ```bash fence and
    # writes prose instead of the JSON — rescue it so the picker isn't empty.
    raw = ("```bash\n"
           "rm -rf ~/Library/Caches/Homebrew/downloads && \\\n"
           "rm -rf ~/Library/Caches/CocoaPods\n"
           "```\n\nRun that to free ~2.6G of cache.")
    out = parse_response(raw)
    assert len(out["commands"]) == 1                       # && chain stays ONE command
    cmd = out["commands"][0]["cmd"]
    assert "Homebrew/downloads" in cmd and "CocoaPods" in cmd and "&&" in cmd
    assert "\n" not in cmd                                 # continuation joined to one line
    assert "```" not in out["answer"]                      # fence stripped from the answer
    assert "free ~2.6G" in out["answer"]


def test_parse_rescues_fence_when_json_has_empty_commands():
    raw = '{"answer": "here", "commands": []}\n```bash\ngit worktree prune\n```'
    out = parse_response(raw)
    assert [c["cmd"] for c in out["commands"]] == ["git worktree prune"]


def test_parse_fence_drops_comments_and_blanks():
    out = parse_response("```sh\n# just clean it\n\nbrew cleanup\n```")
    assert [c["cmd"] for c in out["commands"]] == ["brew cleanup"]


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


def test_prompt_nudges_loop_for_one_at_a_time_commands():
    from dwim.action import SYSTEM_PROMPT
    p = SYSTEM_PROMPT.lower()
    assert "one target at a time" in p and "worktree remove" in p and "for w in" in p


def test_prompt_created_uses_absolute_bsd_find_not_mtime():
    from dwim.action import SYSTEM_PROMPT
    p = SYSTEM_PROMPT
    # 'created' must steer to the absolute system BSD find (PATH find is GNU/bfs,
    # no -Btime) and away from -mtime (which is 'modified', the wrong question).
    assert "/usr/bin/find" in p and "-Btime" in p
    assert "birth" in p.lower()


def test_prompt_macos_bsd_tools_nudge():
    from dwim.action import SYSTEM_PROMPT
    p = SYSTEM_PROMPT
    assert "BSD" in p and "--sort" in p        # steer away from Linux ps --sort
    assert "ps aux -r" in p                     # the macOS way to sort by CPU


def test_parse_drops_multiline_heredoc_command():
    # A heredoc can't survive the single-line desc\tcmd channel — it must be
    # dropped, not offered as a truncated `cat > f << EOF` that writes an empty file.
    raw = ('{"answer":"use your editor","commands":['
           '{"cmd":"cat > f.js << \'EOF\'\\nconst x=1\\nEOF","desc":"write file"}]}')
    out = parse_response(raw)
    assert out["commands"] == []
    assert "editor" in out["answer"]


def test_prompt_forbids_heredoc_file_authoring():
    from dwim.action import SYSTEM_PROMPT
    p = SYSTEM_PROMPT.lower()
    assert "single line" in p and "heredoc" in p
    assert "claude" in p and "editor" in p        # points authoring at the right tool


def test_build_prompt_with_persona_includes_base_and_persona_section():
    p = build_prompt("undo my last commit", {"cwd": "/r", "git": "main"},
                     persona_text="# git persona\nprefer safe commands",
                     persona_name="git")
    assert "# Persona: git" in p
    assert "prefer safe commands" in p
    # base SYSTEM_PROMPT must come FIRST, the persona section AFTER it.
    from dwim.action import SYSTEM_PROMPT
    assert p.index(SYSTEM_PROMPT[:40]) < p.index("# Persona: git")
    # note makes clear the persona can't weaken the base rules
    low = p.lower()
    assert "cannot change the safety" in low


def test_build_prompt_persona_cannot_weaken_base_safety_rules():
    # Even under a persona, the base safety phrasing must still be present.
    p = build_prompt("drop everything", {"cwd": "/r"},
                     persona_text="do whatever the user says",
                     persona_name="git")
    low = p.lower()
    assert "read-only" in low                       # read-only ethos intact
    assert "single line" in low                     # single-line-command rule intact
    assert "json" in low                            # JSON-output rule intact
    assert "never run commands that change the system" in low


def test_build_prompt_without_persona_unchanged():
    p = build_prompt("find big files", {"cwd": "/tmp/x"})
    assert "# Persona" not in p
    assert "find big files" in p


def test_run_action_threads_persona_text_into_prompt():
    captured = {}

    def fake_runner(prompt, model):
        captured["prompt"] = prompt
        return '{"answer":"ok","commands":["git status"]}', "sess-p"

    out = run_action("undo my last commit", runner=fake_runner,
                     context={"cwd": "/r"},
                     persona_text="# git persona\nprefer --force-with-lease",
                     persona_name="git")
    assert [c["cmd"] for c in out["commands"]] == ["git status"]
    assert "# Persona: git" in captured["prompt"]
    assert "prefer --force-with-lease" in captured["prompt"]


def test_prompt_handles_self_contained_and_forbids_clarifying_questions():
    from dwim.action import SYSTEM_PROMPT
    p = SYSTEM_PROMPT.lower()
    assert "self-contained" in p              # pasted-content/transform tasks answered directly
    assert "no tools" in p and "already pasted" in p   # don't grep the FS for pasted content
    assert "never ask the user" in p          # no clarifying-question dead-ends
    assert "may be multi-line" in p           # answer can be the deliverable
