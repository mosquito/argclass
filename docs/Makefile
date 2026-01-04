SPHINXOPTS    ?= -W
SPHINXBUILD   ?= uv run --group docs sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

.PHONY: help clean html latexpdf pdf test all

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  html      Build HTML documentation"
	@echo "  latexpdf  Build PDF documentation (requires LaTeX)"
	@echo "  pdf       Alias for latexpdf"
	@echo "  all       Build PDF, copy to _static, then build HTML"
	@echo "  test      Test documentation examples"
	@echo "  clean     Remove build directory"

html:
	@mkdir -p $(BUILDDIR)/html
	$(SPHINXBUILD) $(SPHINXOPTS) -b html $(SOURCEDIR) $(BUILDDIR)/html

latexpdf:
	@mkdir -p $(BUILDDIR)/latex
	$(SPHINXBUILD) $(SPHINXOPTS) -b latex $(SOURCEDIR) $(BUILDDIR)/latex
	@echo "Running LaTeX..."
	$(MAKE) -C $(BUILDDIR)/latex all-pdf LATEXMKOPTS="-interaction=nonstopmode"
	@echo "PDF available at $(BUILDDIR)/latex/argclass.pdf"

pdf: latexpdf

# Build everything: PDF first, copy to static, then HTML
all: latexpdf
	@echo "Copying PDF to _static..."
	@mkdir -p _static
	cp $(BUILDDIR)/latex/argclass.pdf _static/
	@echo "Building HTML with PDF included..."
	$(MAKE) html
	@echo "Documentation complete:"
	@echo "  HTML: $(BUILDDIR)/html/index.html"
	@echo "  PDF:  $(BUILDDIR)/html/_static/argclass.pdf"

test:
	uv run pytest -svv ../README.md .

clean:
	rm -rf $(BUILDDIR)
