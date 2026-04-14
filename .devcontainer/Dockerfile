FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

ARG IMAGE_VERSION=local
ARG BUILD_DATE=unknown
ARG VCS_REF=unknown

LABEL org.opencontainers.image.title="azure-naming dev container" \
    org.opencontainers.image.description="Development container for the Azure Naming service" \
    org.opencontainers.image.version="${IMAGE_VERSION}" \
    org.opencontainers.image.created="${BUILD_DATE}" \
    org.opencontainers.image.revision="${VCS_REF}"

ARG GO_VERSION=1.22.12
ARG ORAS_VERSION=1.2.2
ARG GH_VERSION=2.74.1
ARG TARGETARCH=amd64

# ── System packages & language runtimes ──────────────────────────────────────
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && mkdir -p /etc/apt/keyrings \
    && curl -sLS https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg \
    && chmod go+r /etc/apt/keyrings/microsoft.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/azure-cli/ bookworm main" > /etc/apt/sources.list.d/azure-cli.list \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends \
        azure-cli \
        iproute2 \
        jq \
        libicu72 \
        lsof \
        make \
        nodejs \
        procps \
        uuid-runtime \
    && npm install -g azure-functions-core-tools@4 azurite \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Go toolchain ─────────────────────────────────────────────────────────────
RUN curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-${TARGETARCH}.tar.gz" -o /tmp/go.tar.gz \
    && tar -C /usr/local -xzf /tmp/go.tar.gz \
    && rm -f /tmp/go.tar.gz
ENV PATH="/usr/local/go/bin:${PATH}"

# ── oras CLI (OCI registry) ──────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/oras-project/oras/releases/download/v${ORAS_VERSION}/oras_${ORAS_VERSION}_linux_${TARGETARCH}.tar.gz" -o /tmp/oras.tar.gz \
    && tar -C /usr/local/bin -xzf /tmp/oras.tar.gz oras \
    && chmod +x /usr/local/bin/oras \
    && rm -f /tmp/oras.tar.gz

# ── GitHub CLI ───────────────────────────────────────────────────────────────
RUN curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${TARGETARCH}.tar.gz" -o /tmp/gh.tar.gz \
    && tar -C /tmp -xzf /tmp/gh.tar.gz \
    && mv "/tmp/gh_${GH_VERSION}_linux_${TARGETARCH}/bin/gh" /usr/local/bin/gh \
    && chmod +x /usr/local/bin/gh \
    && rm -rf /tmp/gh.tar.gz "/tmp/gh_${GH_VERSION}_linux_${TARGETARCH}"