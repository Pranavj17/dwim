#!/usr/bin/env zsh
# Guard-path coverage for _dwim_run_action: bad inputs must bail before ever
# touching the buffer-load seam (_dwim_load).
export PATH="$(mktemp -d):$PATH"
bindir="${PATH%%:*}"

source "$HOME/dotfiles/files/zsh/dwim.zsh"

fail() { print "FAIL: $*"; exit 1 }

# --- Case 1: empty intent never calls dwim-action or _dwim_load -------------
typeset -g _DWIM_LOADED=""
_dwim_load() { _DWIM_LOADED="$1" }

_dwim_run_action ""
rc=$?
(( rc != 0 )) || fail "empty intent returned rc=0, expected non-zero"
[[ -z "$_DWIM_LOADED" ]] || fail "empty intent still called _dwim_load with '$_DWIM_LOADED'"

# --- Case 2: dwim-action producing no output never calls _dwim_load --------
cat > "$bindir/dwim-action" <<'EOF'
#!/usr/bin/env bash
# deliberately prints nothing
EOF
chmod +x "$bindir/dwim-action"

_DWIM_LOADED=""
_dwim_run_action "x"
rc=$?
(( rc != 0 )) || fail "empty dwim-action output returned rc=0, expected non-zero"
[[ -z "$_DWIM_LOADED" ]] || fail "empty dwim-action output still called _dwim_load with '$_DWIM_LOADED'"

print "PASS"
