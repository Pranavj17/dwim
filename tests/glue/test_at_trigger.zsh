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

# Stub fzf to pick the first line; stub the buffer-load seam.
fzf() { head -1 }
typeset -g _DWIM_LOADED=""
_dwim_load() { _DWIM_LOADED="$1" }

_dwim_run_action "find big files"
[[ "$_DWIM_LOADED" == "du -sh *" ]] || { print "FAIL: got '$_DWIM_LOADED'"; exit 1 }
print "PASS"
