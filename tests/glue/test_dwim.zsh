#!/usr/bin/env zsh
set -e
export XDG_CACHE_HOME="$(mktemp -d)"
bindir="$(mktemp -d)"

# Stub dwim-engine on PATH: echoes a fixed correction.
cat > "$bindir/dwim-engine" <<'EOF'
#!/usr/bin/env bash
echo "brew install pip"
EOF
chmod +x "$bindir/dwim-engine"
export PATH="$bindir:$PATH"

source "$HOME/dotfiles/files/zsh/dwim.zsh"

# Detach auto-firing hooks so they don't overwrite our seeded state file.
add-zsh-hook -d preexec _dwim_preexec
precmd_functions=(${precmd_functions:#_dwim_precmd})

# Override the buffer-load seam to capture instead of print -z.
typeset -g _DWIM_LOADED=""
_dwim_load() { _DWIM_LOADED="$1" }

# Seed a failed-command state.
mkdir -p "$XDG_CACHE_HOME/dwim"
print -r -- "127"             >  "$XDG_CACHE_HOME/dwim/last"
print -r -- "brw install pip" >> "$XDG_CACHE_HOME/dwim/last"

dwim
[[ "$_DWIM_LOADED" == "brew install pip" ]] \
  || { print "FAIL: expected suggestion loaded, got '$_DWIM_LOADED'"; exit 1 }

# No state → nothing loaded, nonzero return.
rm -f "$XDG_CACHE_HOME/dwim/last"
_DWIM_LOADED=""
if dwim; then print "FAIL: dwim should return nonzero with no state"; exit 1; fi
[[ -z "$_DWIM_LOADED" ]] || { print "FAIL: loaded despite no state"; exit 1 }

print "PASS"
