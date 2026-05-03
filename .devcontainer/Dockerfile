FROM python:3.12-slim

# Install system packages:
#   postgresql + contrib   — full PostgreSQL server running inside the container
#   libpq-dev              — header files required to build psycopg[binary]
#   build-essential        — gcc/make for Python native extensions
#   ca-certificates        — needed by the NodeSource setup script
#   Developer utilities    — git, curl, openssh-client, ripgrep, jq, fd-find, sudo, wget
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    postgresql \
    postgresql-contrib \
    libpq-dev \
    build-essential \
    git \
    curl \
    wget \
    openssh-client \
    ripgrep \
    jq \
    fd-find \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js LTS via NodeSource (keeps Node managed by apt for easy updates)
# https://github.com/nodesource/distributions
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install pnpm globally (used by src/app)
RUN npm install -g pnpm@latest

# Install GitHub CLI (https://github.com/cli/cli/blob/trunk/docs/install_linux.md)
RUN mkdir -p -m 755 /etc/apt/keyrings && \
    wget -nv -O /tmp/gh-keyring.gpg https://cli.github.com/packages/githubcli-archive-keyring.gpg && \
    cp /tmp/gh-keyring.gpg /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends gh && \
    rm -rf /var/lib/apt/lists/* /tmp/gh-keyring.gpg

# Create the vscode user expected by VS Code Dev Containers (UID 1000).
# Do NOT start PostgreSQL here — that is post-setup.sh's responsibility.
RUN useradd -m -u 1000 -s /bin/bash vscode && \
    echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER vscode