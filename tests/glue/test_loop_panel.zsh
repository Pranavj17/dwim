#!/usr/bin/env zsh
# The loop: a read-only command result is paneled; a mutating candidate is
# confirmed before running; an interactive command is handed to the prompt.
export PATH="$(mktemp -d):$PATH"; bindir="${PATH%%:*}"

# Stub dwim-engine: --run echoes canned JSON per command; --repair echoes a
# mutating candidate. The "brew install"* case is --force-aware: without
# --force it reports the command as not-yet-run (ran:false); with --force it
# logs to $DWIM_TEST_FORCELOG and reports it as run (ran:true). zsh invokes
# this as `dwim-engine --run "$cmd" [--force]`, so --force (if present) lands
# in $3 — but we scan all args ("$@") to be robust either way.
cat > "$bindir/dwim-engine" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "--run" ]]; then
  case "$2" in
    "du -sh ."*) echo '{"cmd":"du -sh .","interactive":false,"read_only":true,"ran":true,"exit":0,"stdout":"1.0M .","stderr":"","timed_out":false}';;
    "ncdu"*)     echo '{"cmd":"ncdu","interactive":true,"read_only":false,"ran":false,"exit":null,"stdout":"","stderr":"","timed_out":false}';;
    "brew install"*)
      forced=0
      for arg in "$@"; do [[ "$arg" == "--force" ]] && forced=1; done
      if (( forced )); then
        echo forced >> "$DWIM_TEST_FORCELOG"
        echo '{"cmd":"brew install ncdu","interactive":false,"read_only":false,"ran":true,"exit":0,"stdout":"installed","stderr":"","timed_out":false}'
      else
        echo '{"cmd":"brew install ncdu","interactive":false,"read_only":false,"ran":false,"exit":null,"stdout":"","stderr":"","timed_out":false}'
      fi
      ;;
  esac
elif [[ "$1" == "--repair" ]]; then
  printf 'install ncdu with Homebrew\tbrew install ncdu\n'
fi
EOF
chmod +x "$bindir/dwim-engine"

source "$HOME/dotfiles/files/zsh/dwim.zsh"

# Record what gets paneled, confirmed, and loaded onto the prompt.
typeset -g PANELED="" CONFIRM_ASKED="" LOADED=""
_dwim_panel() { PANELED+="$1;" }
_dwim_confirm() { CONFIRM_ASKED+="$1;"; return 0 }   # stub: always "yes"
_dwim_load() { LOADED="$1" }

# read-only command → paneled, no confirm
_dwim_execute_loop "du -sh ."
[[ "$PANELED" == *"du -sh ."* ]] || { print "FAIL: read-only not paneled"; exit 1 }
[[ -z "$CONFIRM_ASKED" ]] || { print "FAIL: read-only should not confirm"; exit 1 }

# interactive command → handed to prompt (print -z via _dwim_load), not paneled
CONFIRM_ASKED=""; PANELED=""; LOADED=""
_dwim_execute_loop "ncdu"
[[ "$LOADED" == "ncdu" ]] || { print "FAIL: interactive not handed to prompt"; exit 1 }

# --- Safety-critical: mutating command must only reach --force AFTER confirm
# succeeds; on refusal, --force must never be invoked and the loop stops. ---

# Scenario A — confirm YES: --force runs, but only after confirm was asked.
export DWIM_TEST_FORCELOG="$(mktemp)"
CONFIRM_ASKED=""; PANELED=""; LOADED=""
_dwim_confirm() { CONFIRM_ASKED+="$1;"; return 0 }   # user pressed Enter
_dwim_execute_loop "brew install ncdu"
[[ "$CONFIRM_ASKED" == *"brew install ncdu"* ]] || { print "FAIL: confirm not asked for mutating command"; exit 1 }
[[ -s "$DWIM_TEST_FORCELOG" ]] || { print "FAIL: --force was never invoked after confirm=yes"; exit 1 }

# Scenario B — confirm NO (Esc): --force must NEVER be invoked; loop stops.
export DWIM_TEST_FORCELOG="$(mktemp)"
CONFIRM_ASKED=""; PANELED=""; LOADED=""
_dwim_confirm() { CONFIRM_ASKED+="$1;"; return 1 }   # user pressed Esc
_dwim_execute_loop "brew install ncdu"
[[ -z "$(cat "$DWIM_TEST_FORCELOG")" ]] || { print "FAIL: --force was invoked despite confirm=no"; exit 1 }

print "PASS"
