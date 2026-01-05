SPHINXOPTS    ?= -W
SPHINXBUILD   ?= uv run --group docs sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build
DOCKER_IMAGE  = argclass-docs

.PHONY: help clean html latexpdf pdf docker-pdf test all

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  html       Build HTML documentation"
	@echo "  latexpdf   Build PDF documentation (requires LaTeX)"
	@echo "  pdf        Alias for latexpdf"
	@echo "  docker-pdf Build PDF using Docker (no local LaTeX needed)"
	@echo "  all        Build PDF, copy to _static, then build HTML"
	@echo "  test       Test documentation examples"
	@echo "  clean      Remove build directory"

html:
	@mkdir -p $(BUILDDIR)/html
	$(SPHINXBUILD) $(SPHINXOPTS) -b html $(SOURCEDIR) $(BUILDDIR)/html

latexpdf:
	@mkdir -p $(BUILDDIR)/latex
	$(SPHINXBUILD) $(SPHINXOPTS) -b latex $(SOURCEDIR) $(BUILDDIR)/latex
	@echo "Running LaTeX..."
	-$(MAKE) -C $(BUILDDIR)/latex all-pdf LATEXMKOPTS="-f -interaction=nonstopmode"
	@test -f $(BUILDDIR)/latex/argclass.pdf || (echo "ERROR: PDF not generated" && exit 1)
	@echo "PDF available at $(BUILDDIR)/latex/argclass.pdf"

pdf: latexpdf

# Build PDF using Docker (no local LaTeX installation needed)
docker-pdf:
	@echo "Building Docker image..."
	docker build -t $(DOCKER_IMAGE) -f Dockerfile ..
	@echo "Installing dependencies and building LaTeX sources..."
	docker run --rm -v $(CURDIR)/..:/project -w /project $(DOCKER_IMAGE) \
		sh -c "uv sync --group docs && uv run --group docs sphinx-build -W -b latex docs docs/_build/latex"
	@echo "Running LaTeX..."
	-docker run --rm -v $(CURDIR)/..:/project -w /project/docs/_build/latex $(DOCKER_IMAGE) \
		make all-pdf LATEXMKOPTS="-f -interaction=nonstopmode"
	@test -f $(BUILDDIR)/latex/argclass.pdf || (echo "ERROR: PDF not generated" && exit 1)
	@echo "PDF available at $(BUILDDIR)/latex/argclass.pdf"

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

clean: docker-clean
	rm -rf $(BUILDDIR)
	-docker rmi $(DOCKER_IMAGE)
