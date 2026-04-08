FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

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
        libicu72 \
        lsof \
        nodejs \
        procps \
    && npm install -g azure-functions-core-tools@4 azurite \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*