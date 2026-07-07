# dwim install: symlink the CLI entrypoints into ~/.local/bin (which is on PATH).
# Re-run after adding a new bin/dwim-* entry — idempotent (ln -sf overwrites).
# Until now these links were created by hand, so a rebuild/new laptop lost them
# (and a new bin like dwim-locate wasn't picked up); this makes them reproducible.
PREFIX ?= $(HOME)/.local/bin
BINS := $(notdir $(wildcard bin/dwim-*))

.PHONY: install uninstall test

install:
	@mkdir -p "$(PREFIX)"
	@for b in $(BINS); do \
		ln -sf "$(CURDIR)/bin/$$b" "$(PREFIX)/$$b"; \
		echo "linked $(PREFIX)/$$b -> $(CURDIR)/bin/$$b"; \
	done

uninstall:
	@for b in $(BINS); do rm -f "$(PREFIX)/$$b"; echo "removed $(PREFIX)/$$b"; done

test:
	/opt/homebrew/bin/python3 -m pytest -q
