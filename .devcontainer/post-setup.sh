#!/usr/bin/env bash
# Dev Container Post-Setup Script
# Runs once when the container is first created.
# Starts PostgreSQL, initialises the dev and test databases, installs the
# Python package in editable mode, runs Alembic migrations, and configures
# developer-experience aliases.

set -euo pipefail

# --- Colors ---
CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RESET='\033[0m'

step() { echo -e "${CYAN}[*] $1${RESET}"; }
ok()   { echo -e "${GREEN}[+] $1${RESET}"; }
warn() { echo -e "${YELLOW}[!] $1${RESET}"; }

# Ensure pip-installed scripts (e.g. ctpool) are on PATH for this script
export PATH="$HOME/.local/bin:$PATH"

# ---------------------------------------------------------------------------
# 1. Start PostgreSQL
#
# The devcontainer.json bind-mounts ./data/postgres → /var/lib/postgresql so
# that the database persists across container rebuilds on the developer's
# workstation.  This creates two first-run concerns:
#
#   a) Ownership: the bind-mounted directory is created by Docker as root or
#      by the host user (UID 1000).  PostgreSQL requires the data directory to
#      be owned by the postgres system user (UID 999).  Fix unconditionally.
#
#   b) Cluster init: if the directory is empty (first ever run), we must
#      initialise the cluster before starting the service.
# ---------------------------------------------------------------------------
step "Fixing PostgreSQL data directory ownership"
sudo chown -R postgres:postgres /var/lib/postgresql

# Detect the installed PostgreSQL major version (e.g. 15, 16) dynamically so
# this script does not break when the Dockerfile upgrades PostgreSQL.
PG_VERSION=$(pg_lsclusters --no-header 2>/dev/null | awk '{print $1; exit}' || true)
if [[ -z "$PG_VERSION" ]]; then
    # Fallback: ask the pg_config binary
    PG_VERSION=$(pg_config --version 2>/dev/null | grep -oP '\d+' | head -1 || echo "15")
fi
CLUSTER_DATA="/var/lib/postgresql/${PG_VERSION}/main"

if [[ ! -f "${CLUSTER_DATA}/PG_VERSION" ]]; then
    step "Initialising PostgreSQL cluster data directory (first run)"
    # The cluster config in /etc/postgresql/ was created by apt install postgresql
    # during the Docker image build.  The bind mount on /var/lib/postgresql
    # shadows that pre-built data directory with an empty host directory, so the
    # data must be re-initialised.  We use initdb directly rather than
    # pg_ctlcluster because the `initdb` action is not supported on all Debian
    # versions of pg_ctlcluster.
    sudo mkdir -p "${CLUSTER_DATA}"
    sudo chown postgres:postgres "${CLUSTER_DATA}"
    # Clear any stale files from a previous failed or partial init.
    # find -mindepth 1 deletes contents without removing the directory itself.
    if [[ -n "$(sudo ls -A "${CLUSTER_DATA}" 2>/dev/null)" ]]; then
        warn "Cluster directory is non-empty but uninitialised — clearing stale data"
        sudo find "${CLUSTER_DATA}" -mindepth 1 -delete
    fi
    sudo -u postgres /usr/lib/postgresql/${PG_VERSION}/bin/initdb -D "${CLUSTER_DATA}"
    ok "Cluster ${PG_VERSION}/main data initialised"
else
    ok "PostgreSQL cluster already initialised — reusing existing data"
fi

step "Starting PostgreSQL service"
sudo service postgresql start

# Wait up to 30 seconds for PostgreSQL to accept connections
for i in $(seq 1 30); do
    if pg_isready -q 2>/dev/null; then
        ok "PostgreSQL is ready"
        break
    fi
    if [[ "$i" -eq 30 ]]; then
        echo "ERROR: PostgreSQL did not become ready within 30 seconds" >&2
        exit 1
    fi
    sleep 1
done

# ---------------------------------------------------------------------------
# 2. Create ctpool role and databases (idempotent)
# ---------------------------------------------------------------------------
step "Initialising ctpool and ctpool_test databases"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<'SQL'
-- Only create the role if it does not already exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ctpool') THEN
        CREATE ROLE ctpool WITH LOGIN PASSWORD 'ctpool';
    END IF;
END$$;

-- Main development database (used by the running application)
SELECT 'CREATE DATABASE ctpool OWNER ctpool'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ctpool') \gexec

-- Dedicated test database (required by the pytest suite — do NOT point tests at ctpool)
SELECT 'CREATE DATABASE ctpool_test OWNER ctpool'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ctpool_test') \gexec
SQL
ok "Databases ready: ctpool, ctpool_test"

# ---------------------------------------------------------------------------
# 3. Install the Python package in editable mode
# ---------------------------------------------------------------------------
step "Installing ctpool[dev] package"
if [[ -d "./src/ctpool" ]]; then
    pip install -q --upgrade pip
    pip install -q -e "./src/ctpool[dev]"
    ok "ctpool installed: $(ctpool --version 2>/dev/null || echo 'version unknown')"
else
    warn "src/ctpool not found — skipping install"
    warn "Run once the source tree exists: pip install -e src/ctpool[dev]"
fi

# ---------------------------------------------------------------------------
# 4. Run database migrations
# ---------------------------------------------------------------------------
step "Running Alembic migrations"
if command -v ctpool >/dev/null 2>&1; then
    ctpool db-init && ok "Migrations applied"
else
    warn "ctpool CLI not found — skipping migrations"
    warn "Run manually: cd src/ctpool && alembic upgrade head"
fi

# ---------------------------------------------------------------------------
# 5. Install frontend dependencies (src/app)
# ---------------------------------------------------------------------------
step "Installing frontend dependencies"
if [[ -d "./src/app" ]]; then
    (cd src/app && pnpm install) && ok "Frontend dependencies installed"
else
    warn "src/app not found — skipping pnpm install"
    warn "Run once the source tree exists: cd src/app && pnpm install"
fi

# ---------------------------------------------------------------------------
# 6. Install semgrep for security scanning (optional)
#    Use pipx so semgrep's dependencies are fully isolated and cannot
#    downgrade packages (e.g. click) that ctpool depends on.
# ---------------------------------------------------------------------------
if ! command -v semgrep >/dev/null 2>&1; then
    step "Installing semgrep (security scanner)"
    pip install -q --user pipx 2>/dev/null || true
    pipx install semgrep && ok "semgrep installed" || warn "semgrep install failed — skipping"
fi

# ---------------------------------------------------------------------------
# 7. Developer-experience aliases
# ---------------------------------------------------------------------------
if ! grep -Fq '# === BitsysCerts Development Aliases ===' "$HOME/.bashrc"; then
    step "Adding development aliases"
    cat >> "$HOME/.bashrc" << 'EOF'

# === BitsysCerts Development Aliases ===
export PATH="$HOME/.local/bin:$PATH"
alias ll="ls -la"
alias fd="fdfind"
alias sg="semgrep"

# ctpool shortcuts (run from any directory)
alias ct="ctpool"
alias ct-test="(cd ~/workspaces/bitsyscerts/src/ctpool 2>/dev/null || cd /workspaces/bitsyscerts/src/ctpool) && pytest"
alias ct-lint="(cd ~/workspaces/bitsyscerts/src/ctpool 2>/dev/null || cd /workspaces/bitsyscerts/src/ctpool) && ruff check ctpool/"
alias ct-type="(cd ~/workspaces/bitsyscerts/src/ctpool 2>/dev/null || cd /workspaces/bitsyscerts/src/ctpool) && mypy ctpool/"
alias ct-db="psql postgresql://ctpool:ctpool@localhost:5432/ctpool"
alias ct-testdb="psql postgresql://ctpool:ctpool@localhost:5432/ctpool_test"

# Frontend shortcuts
alias app="cd /workspaces/bitsyscerts/src/app"
alias app-dev="(cd /workspaces/bitsyscerts/src/app && pnpm dev)"
alias app-test="(cd /workspaces/bitsyscerts/src/app && pnpm test)"
alias app-lint="(cd /workspaces/bitsyscerts/src/app && pnpm lint)"

# Colorful prompt
PS1='\[\033[38;5;39m\]\u\[\033[0m\]@\[\033[38;5;42m\]\h\[\033[0m\] \[\033[38;5;244m\]\w\[\033[0m\]\n\$ '
# === End BitsysCerts Development Aliases ===
EOF
fi

# ---------------------------------------------------------------------------
# 8. Install OSV Scanner (SCA)
# ---------------------------------------------------------------------------
step "Installing OSV Scanner (software composition analysis)"
ARCH=$(dpkg --print-architecture 2>/dev/null || echo "amd64")
sudo curl -sSfL \
    "https://github.com/google/osv-scanner/releases/latest/download/osv-scanner_linux_${ARCH}" \
    -o /usr/local/bin/osv-scanner
sudo chmod +x /usr/local/bin/osv-scanner
ok "OSV Scanner $(osv-scanner --version 2>&1 | head -1) installed"

# ---------------------------------------------------------------------------
# 9. Install Trivy (CVA)
# ---------------------------------------------------------------------------
step "Installing Trivy (container vulnerability analysis)"
ARCH=$(dpkg --print-architecture 2>/dev/null || echo "amd64")
[[ "$ARCH" == "arm64" ]] && TRIVY_ARCH="Linux-ARM64" || TRIVY_ARCH="Linux-64bit"
TRIVY_VERSION=$(curl -fsSL https://api.github.com/repos/aquasecurity/trivy/releases/latest \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'].lstrip('v'))")
curl -fsSL \
    "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_${TRIVY_ARCH}.tar.gz" \
    | sudo tar -xzf - -C /usr/local/bin trivy
ok "Trivy $(trivy --version 2>&1 | head -1) installed"


ok "Development environment setup complete!"
echo ""
echo "  Python / ctpool:"
echo "    ct-test   — pytest (with ruff + mypy)"
echo "    ct-lint   — ruff check only"
echo "    ct-type   — mypy check only"
echo "    ct-db     — psql into the dev database"
echo "    ct-testdb — psql into the test database"
echo ""
echo "  React / Vite:"
echo "    app-dev   — pnpm dev (Vite dev server on :5173)"
echo "    app-test  — pnpm test (Vitest)"
echo "    app-lint  — pnpm lint (ESLint)"
