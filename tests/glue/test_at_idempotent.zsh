#!/usr/bin/env zsh
# Sourcing dwim.zsh twice must NOT make _dwim_orig_accept_line point at our own wrapper.
autoload -Uz add-zsh-hook
zmodload zsh/zle 2>/dev/null

# Stub things dwim.zsh may reference so sourcing is side-effect-free.
DWIM_ICON="x"

src="$HOME/dotfiles/files/zsh/dwim.zsh"
source "$src"
source "$src"   # second source must be a no-op for the accept-line wrapper

# After double-source: our widget is installed, and the saved original is NOT our wrapper.
if [[ "${widgets[accept-line]}" == user:_dwim_at_accept \
   && "${widgets[_dwim_orig_accept_line]}" != user:_dwim_at_accept ]]; then
  print "PASS"
else
  print "FAIL: accept-line=${widgets[accept-line]} orig=${widgets[_dwim_orig_accept_line]}"
  exit 1
fi
