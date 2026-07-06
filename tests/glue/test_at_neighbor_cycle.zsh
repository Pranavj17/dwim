#!/usr/bin/env zsh
# A second `source ~/.zshrc` re-sources dwim.zsh AND a neighbor plugin that also
# wraps accept-line. dwim's install must not form a widget cycle (infinite loop on Enter).
autoload -Uz add-zsh-hook
zmodload zsh/zle 2>/dev/null
DWIM_ICON="x"
src="$HOME/dotfiles/files/zsh/dwim.zsh"

# A neighbor plugin using the same self-guarded delegation idiom (like zsh-syntax-highlighting).
_load_neighbor() {
  if [[ -z "$_NBR_INSTALLED" ]]; then
    zle -A accept-line _nbr_orig_accept_line
    _nbr_accept() { zle _nbr_orig_accept_line }
    zle -N accept-line _nbr_accept
    typeset -g _NBR_INSTALLED=1
  fi
}

# Simulate: rc load #1 (dwim, then neighbor on top), then rc load #2 (both again).
source "$src"; _load_neighbor
source "$src"; _load_neighbor

# Walk the accept-line chain following each wrapper to its saved original.
# Known saved-original alias names for our two wrappers:
typeset -A orig_of
orig_of[_dwim_at_accept]=_dwim_orig_accept_line
orig_of[_nbr_accept]=_nbr_orig_accept_line

cur="accept-line"
integer hops=0
typeset -A seen
while (( hops < 20 )); do
  w="${widgets[$cur]}"          # e.g. "user:_dwim_at_accept" or "builtin"
  [[ "$w" == builtin* || -z "$w" ]] && { print "PASS"; exit 0 }
  fn="${w#user:}"
  if [[ -n "${seen[$fn]}" ]]; then
    print "FAIL: cycle detected at $fn (chain loops)"; exit 1
  fi
  seen[$fn]=1
  cur="${orig_of[$fn]}"
  [[ -z "$cur" ]] && { print "PASS"; exit 0 }   # unknown wrapper's original = chain end for our purposes
  (( hops++ ))
done
print "FAIL: chain did not terminate in 20 hops"; exit 1
