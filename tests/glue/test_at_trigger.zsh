#!/usr/bin/env zsh
# Verify a leading '@' line is diverted to the action handler, not run as a command.
export PATH="$(mktemp -d):$PATH"
bindir="${PATH%%:*}"
cat > "$bindir/dwim-action" <<'EOF'
#!/usr/bin/env bash
echo "du -sh *"
EOF
chmod +x "$bindir/dwim-action"

source "$HOME/dotfiles/files/zsh/dwim.zsh"

# Stub fzf to pick the first line; stub the execute-loop seam (the picked
# command now drives run→observe→repair instead of loading straight onto
# the prompt — this test asserts the routing, not the loop's internals).
fzf() { head -1 }
typeset -g _DWIM_LOOP_CALLED=""
_dwim_execute_loop() { _DWIM_LOOP_CALLED="$1" }

_dwim_run_action "find big files"
[[ "$_DWIM_LOOP_CALLED" == "du -sh *" ]] || { print "FAIL: got '$_DWIM_LOOP_CALLED'"; exit 1 }
print "PASS"
