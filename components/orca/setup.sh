#!/bin/bash

# Orca setup hook for a temba-components worktree.
# Symlinks shared utility files from nyaruka/utils, ensures the devcontainer
# is built/running (recreating it if the bind mounts are stale), and installs
# bun dependencies inside the worktree.
#
# Usage:
#   ./orca/setup.sh                  # run directly
#   (orca invokes this via orca.yaml's scripts.setup)

set -e

CONTAINER_NAME="temba-components"

# Orca exports ORCA_WORKTREE_PATH when running this as a hook; otherwise
# derive the worktree path from the script location.
if [ -n "${ORCA_WORKTREE_PATH:-}" ]; then
    SCRIPT_DIR="$ORCA_WORKTREE_PATH"
else
    SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
fi
WORKSPACE_NAME="$(basename "$SCRIPT_DIR")"

# Pin WORKTREES to the orca workspaces dir so .devcontainer/devcontainer.json
# (which reads ${localEnv:WORKTREES}) sees the orca tree, not a stale value
# inherited from the user's shell.
WORKTREES="$(dirname "$(dirname "$SCRIPT_DIR")")"
export WORKTREES

# Symlink shared files from nyaruka/utils into the worktree (gitignored).
UTILS_DIR="${UTILS_PATH:-$HOME/code/nyaruka/utils}/projects/temba-components"
if [ ! -d "$UTILS_DIR" ]; then
    echo "Error: utils dir not found at $UTILS_DIR (set UTILS_PATH to override)"
    exit 1
fi
for file in run.sh AGENTS.md; do
    if [ -f "$UTILS_DIR/$file" ] && [ ! -e "$SCRIPT_DIR/$file" ]; then
        ln -s "$UTILS_DIR/$file" "$SCRIPT_DIR/$file"
    fi
done
if [ ! -e "$SCRIPT_DIR/CLAUDE.md" ]; then
    ln -s "$UTILS_DIR/AGENTS.md" "$SCRIPT_DIR/CLAUDE.md"
fi

# Ensure the devcontainer is running. Bind mounts can't be edited after the
# container is created, so if an existing container's /workspaces/worktrees
# mount doesn't match $WORKTREES (e.g. a stale conductor-era container),
# recreate it to pick up the new mount.
state="$(docker inspect -f '{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null || true)"

if [ -n "$state" ]; then
    current_worktrees="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/workspaces/worktrees"}}{{.Source}}{{end}}{{end}}' "$CONTAINER_NAME" 2>/dev/null || true)"
    if [ -n "$current_worktrees" ] && [ "$current_worktrees" != "$WORKTREES" ]; then
        echo "Container '$CONTAINER_NAME' has a stale /workspaces/worktrees mount:"
        echo "  $current_worktrees (expected $WORKTREES)"
        echo "Removing and recreating the container..."
        docker rm -f "$CONTAINER_NAME" >/dev/null
        state=""
    fi
fi

case "$state" in
    running) ;;
    "")
        echo "Container '$CONTAINER_NAME' does not exist — building devcontainer..."
        devcontainer up --workspace-folder "$SCRIPT_DIR"
        ;;
    *)
        echo "Container '$CONTAINER_NAME' is $state — starting..."
        docker start "$CONTAINER_NAME"
        ;;
esac

# Install dependencies inside the worktree.
docker exec "$CONTAINER_NAME" bash -c '
    cd "/workspaces/worktrees/temba-components/'"$WORKSPACE_NAME"'"
    bun install
'

echo "Worktree '$WORKSPACE_NAME' ready for development"
