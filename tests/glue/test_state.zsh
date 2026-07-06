#!/usr/bin/env zsh
# NOTE: no `set -e` — we deliberately simulate non-zero exits, which errexit
# would abort on before the assertions run.
export XDG_CACHE_HOME="$(mktemp -d)"
source "$HOME/dotfiles/files/zsh/dwim.zsh"

# Detach the auto-firing hooks so our manual invocations drive the functions
# cleanly (zsh fires preexec/precmd around the test's own statements otherwise).
add-zsh-hook -d preexec _dwim_preexec
precmd_functions=(${precmd_functions:#_dwim_precmd})

state="$XDG_CACHE_HOME/dwim/last"

# Simulate: user runs a failing command.
_dwim_preexec "brw install pip"
( exit 127 ); _dwim_precmd

[[ -f "$state" ]] || { print "FAIL: state file not written"; exit 1 }
[[ "$(sed -n 1p "$state")" == "127" ]] || { print "FAIL: exit code"; exit 1 }
[[ "$(sed -n '2,$p' "$state")" == "brw install pip" ]] || { print "FAIL: cmd"; exit 1 }

# Simulate: running `dwim` must NOT overwrite the state.
_dwim_preexec "dwim"
( exit 0 ); _dwim_precmd
[[ "$(sed -n '2,$p' "$state")" == "brw install pip" ]] \
  || { print "FAIL: dwim invocation clobbered state"; exit 1 }

print "PASS"
