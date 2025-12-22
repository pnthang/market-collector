#!/usr/bin/env bash
set -euo pipefail

# setup_ubuntu.sh
# Usage:
#   - Preferred (avoid shell history expansion when secrets contain '!'):
#       Create a file at "$HOME/.market_collector_env" with the following contents:
#         GITHUB_PAT=ghp_xxx
#         DB_CONN='postgresql+psycopg2://user:pass@host:5432/db'
#       Then run:
#         ./scripts/setup_ubuntu.sh
#
#   - Alternatively, export env vars before running (beware of interactive history expansion):
#       export GITHUB_PAT=ghp_xxx
#       export DB_CONN='postgresql+psycopg2://user:pass@host:5432/db'
#       ./scripts/setup_ubuntu.sh [--branch main] [--image market-collector:latest] [--container market-collector]
#
# This script will:
#  - clone the repository `pnthang/market-collector` from GitHub using a PAT
#  - build a Docker image
#  - run a container with the provided `DB_CONN` set as `DATABASE_URL` env var

REPO=pnthang/market-collector
DEFAULT_BRANCH=main
IMAGE_NAME=market-collector:latest
CONTAINER_NAME=market-collector

print_usage() {
  cat <<EOF
Usage: GITHUB_PAT=... DB_CONN=... ${0} [--branch BRANCH] [--image IMAGE] [--container NAME]

Environment variables required:
  GITHUB_PAT   Personal Access Token with repo read access
  DB_CONN      Database connection string to pass as DATABASE_URL into container

Options:
  --branch BRANCH      Git branch to checkout (default: ${DEFAULT_BRANCH})
  --image IMAGE        Docker image name (default: ${IMAGE_NAME})
  --container NAME     Docker container name (default: ${CONTAINER_NAME})
EOF
}

# parse args
BRANCH=${DEFAULT_BRANCH}
while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch)
      BRANCH="$2"; shift 2;;
    --image)
      IMAGE_NAME="$2"; shift 2;;
    --container)
      CONTAINER_NAME="$2"; shift 2;;
    --help|-h)
      print_usage; exit 0;;
    *)
      echo "Unknown arg: $1"; print_usage; exit 1;;
  esac
done

if [[ -z "${GITHUB_PAT:-}" ]]; then
  echo "Error: GITHUB_PAT environment variable is required" >&2
  print_usage
  exit 2
fi

if [[ -z "${DB_CONN:-}" ]]; then
  echo "Error: DB_CONN environment variable is required (database connection string)" >&2
  print_usage
  exit 2
fi

WORKDIR="/opt/market-collector"

# Allow providing secrets via an env file to avoid typing secrets with shell history
# expansion (e.g. '!' causing "event not found"). The script will look for
# `.market_collector_env` in the following order and source the first match:
#  1. Same directory as this script
#  2. Current working directory
#  3. User's home directory (`$HOME`)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_CANDIDATES=("${SCRIPT_DIR}/.market_collector_env" "$(pwd)/.market_collector_env" "$HOME/.market_collector_env")
ENV_FILE=""
for f in "${ENV_CANDIDATES[@]}"; do
  if [[ -f "${f}" ]]; then
    ENV_FILE="${f}"
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    break
  fi
done

# If variables still not set, prompt interactively (GITHUB_PAT hidden)
if [[ -z "${GITHUB_PAT:-}" ]]; then
  echo "GITHUB_PAT not set. You can set it in ${ENV_FILE} to avoid interactive prompts."
  read -s -p "Enter GITHUB_PAT (input hidden): " GITHUB_PAT
  echo
fi

if [[ -z "${DB_CONN:-}" ]]; then
  echo "DB_CONN not set. You can set it in ${ENV_FILE} to avoid interactive prompts."
  read -p "Enter DB_CONN (e.g. postgresql+psycopg2://user:pass@host:5432/db): " DB_CONN
fi

echo "Starting setup: repo=${REPO} branch=${BRANCH} image=${IMAGE_NAME} container=${CONTAINER_NAME}"

# ensure docker available
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not found — installing docker.io (requires sudo)"
  sudo apt-get update
  sudo apt-get install -y docker.io
  sudo systemctl enable --now docker
fi

# ensure git
if ! command -v git >/dev/null 2>&1; then
  echo "git not found — installing git"
  sudo apt-get update
  sudo apt-get install -y git
fi

# clone or update repo using PAT
if [[ -d "$WORKDIR/.git" ]]; then
  echo "Repository exists at $WORKDIR — pulling latest"
  pushd "$WORKDIR" >/dev/null
  git fetch origin
  git checkout "$BRANCH"
  git pull origin "$BRANCH"
  popd >/dev/null
else
  echo "Cloning repository into $WORKDIR"
  sudo mkdir -p $(dirname "$WORKDIR")
  sudo chown "$USER":"$USER" $(dirname "$WORKDIR") || true
  git clone --depth 1 --branch "$BRANCH" "https://$GITHUB_PAT@github.com/$REPO.git" "$WORKDIR"
fi

pushd "$WORKDIR" >/dev/null

echo "Building Docker image: $IMAGE_NAME"
docker build -t "$IMAGE_NAME" .

echo "Stopping and removing any existing container named $CONTAINER_NAME"
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  docker rm -f "$CONTAINER_NAME" || true
fi

echo "Running container $CONTAINER_NAME"
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -e DATABASE_URL="$DB_CONN" \
  "$IMAGE_NAME"

echo "Setup complete. Container started:"
docker ps --filter "name=$CONTAINER_NAME" --format "{{.ID}}  {{.Image}}  {{.Status}}  {{.Names}}"

popd >/dev/null

exit 0
