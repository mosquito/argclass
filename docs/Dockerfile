FROM python:3.13-slim

# Install LaTeX (full distribution) and required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-full \
    latexmk \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install uv for Python dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /project
