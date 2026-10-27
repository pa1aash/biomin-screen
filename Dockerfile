# Base image pinned by digest (python:3.12.13-slim-bookworm, multi-architecture index).
FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends make fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /repo
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .
CMD ["make", "all"]
