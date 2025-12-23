#!/usr/bin/env bash
set -euo pipefail

# setup-ubuntu-full.sh
# Clone the repository (using GITHUB_PAT if provided) and run
# docker-compose.full.yml to bring up the full stack (web, worker, db, redis).

REPO=pnthang/market-collector
DEFAULT_BRANCH=main
WORKDIR=/opt/market-collector
COMPOSE_FILE=docker-compose.full.yml

# OPTIONAL: you can place a GitHub Personal Access Token here for non-interactive
# runs. WARNING: hardcoding secrets in source is NOT recommended. Prefer exporting
# `GITHUB_PAT` in the environment or using a secrets manager.
# Example to set in-file (replace with your token) -- DO NOT COMMIT:
# INCODE_GITHUB_PAT="ghp_xxx"
INCODE_GITHUB_PAT=""

print_usage() {
  cat <<EOF
Usage: GITHUB_PAT=... ./scripts/setup-ubuntu-full.sh [--branch BRANCH] [--no-build]

Environment (optional):
  GITHUB_PAT   Personal Access Token (if repo is private)
  INCODE_GITHUB_PAT  Optional token embedded in this script (not recommended)

Options:
  --branch BRANCH    Git branch to checkout (default: ${DEFAULT_BRANCH})
  --no-build         Run `docker compose up -d` without forcing a build
EOF
}

BRANCH=${DEFAULT_BRANCH}
NO_BUILD=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch)
      BRANCH="$2"; shift 2;;
    --no-build)
      NO_BUILD=1; shift 1;;
    --help|-h)
      print_usage; exit 0;;
    *)
      echo "Unknown arg: $1"; print_usage; exit 1;;
  esac
done

if [[ -z "${GITHUB_PAT:-}" ]]; then
  # Prefer an explicit env var; fall back to an in-script token if present
  if [[ -n "${INCODE_GITHUB_PAT:-}" ]]; then
    echo "Using in-script GITHUB PAT (INCODE_GITHUB_PAT) for cloning -- ensure this is intentional."
    GITHUB_PAT="${INCODE_GITHUB_PAT}"
  else
    echo "GITHUB_PAT not set. If the repo is private, you'll be prompted to enter it."
    read -s -p "Enter GITHUB_PAT (leave empty to clone anonymously): " maybe_pat
    echo
    if [[ -n "$maybe_pat" ]]; then
      GITHUB_PAT="$maybe_pat"
    fi
  fi
fi

echo "Ensuring required packages: docker, docker-compose-plugin, git"
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y docker.io docker-compose-plugin git
  sudo systemctl enable --now docker
else
  echo "Docker present"
fi

if ! command -v git >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y git
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Clone or update repository
if [[ -d "${WORKDIR}/.git" ]]; then
  echo "Repository exists at ${WORKDIR} — updating"
  pushd "${WORKDIR}" >/dev/null
  git fetch origin
  git checkout "${BRANCH}" || git checkout -b "${BRANCH}" origin/"${BRANCH}" || true
  git pull origin "${BRANCH}" || true
  popd >/dev/null
else
  echo "Cloning repository into ${WORKDIR}"
  sudo mkdir -p "$(dirname "${WORKDIR}")"
  sudo chown "$USER":"$USER" "$(dirname "${WORKDIR}")" || true
  if [[ -n "${GITHUB_PAT:-}" ]]; then
    git clone --depth 1 --branch "${BRANCH}" "https://$GITHUB_PAT@github.com/$REPO.git" "$WORKDIR"
  else
    git clone --depth 1 --branch "${BRANCH}" "https://github.com/$REPO.git" "$WORKDIR"
  fi
fi

pushd "${WORKDIR}" >/dev/null

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "Error: ${COMPOSE_FILE} not found in ${WORKDIR}" >&2
  echo "Ensure you are pointing to the correct repository and branch." >&2
  exit 2
fi

echo "Stopping and removing any existing compose stack (if present)"
# best-effort stop/remove prior containers to ensure a clean start
docker compose -f "${COMPOSE_FILE}" down --remove-orphans --volumes || true

echo "Starting compose stack using ${COMPOSE_FILE}"
if [[ "${NO_BUILD}" -eq 1 ]]; then
  docker compose -f "${COMPOSE_FILE}" up -d
else
  docker compose -f "${COMPOSE_FILE}" up -d --build
fi

echo "Compose stack started. Use 'docker compose -f ${COMPOSE_FILE} ps' to check services."

popd >/dev/null

exit 0
