FROM python:3.13-slim

LABEL org.opencontainers.image.source="https://github.com/mosquito/argclass"
LABEL org.opencontainers.image.description="LaTeX build environment for argclass docs"

# Install LaTeX (full distribution) and required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-full \
    latexmk \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install uv for Python dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /project
