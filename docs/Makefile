SPHINXOPTS    ?= -W
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

.PHONY: help clean html test

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  html    Build HTML documentation"
	@echo "  test    Test documentation examples"
	@echo "  clean   Remove build directory"

html:
	$(SPHINXBUILD) $(SPHINXOPTS) -b html $(SOURCEDIR) $(BUILDDIR)/html

test:
	pytest -svv ../README.md .

clean:
	rm -rf $(BUILDDIR)
