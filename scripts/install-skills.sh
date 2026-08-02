#!/usr/bin/env bash
# install-skills.sh — expose project skills globally via symlinks.
#
# Usage:
#   ./scripts/install-skills.sh          # install (idempotent)
#   ./scripts/install-skills.sh --remove # remove symlinks
#   ./scripts/install-skills.sh --list   # list managed symlinks
#
# Skills are symlinked from .devin/skills/<name> into the global Windsurf
# skills directory (~/.codeium/windsurf/skills/<name>). Edits in the repo
# are live — no re-install needed.
#
# Cross-platform: on Windows, run via Git Bash or WSL. For native PowerShell,
# use scripts/install-skills.ps1 (uses junctions, no admin required).

set -euo pipefail

# --- Config --------------------------------------------------------------

# Skills to expose globally (one directory name per line under .devin/skills/).
SKILLS=(
  dcr-conversation
)

# Global skills directory (Windsurf channel — read by Devin via import).
GLOBAL_SKILLS_DIR="${HOME}/.codeium/windsurf/skills"

# --- Helpers -------------------------------------------------------------

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

link_skill() {
  local name="$1"
  local src="${repo_root}/.devin/skills/${name}"
  local dst="${GLOBAL_SKILLS_DIR}/${name}"

  if [[ ! -d "${src}" ]]; then
    echo "  SKIP ${name} — source not found at ${src}" >&2
    return 1
  fi

  # Remove existing link/dir/file at dst (only if it's a symlink or empty dir).
  if [[ -L "${dst}" ]]; then
    rm "${dst}"
  elif [[ -d "${dst}" ]]; then
    if [[ -z "$(ls -A "${dst}" 2>/dev/null)" ]]; then
      rmdir "${dst}"
    else
      echo "  SKIP ${name} — ${dst} exists and is non-empty" >&2
      return 1
    fi
  elif [[ -e "${dst}" ]]; then
    echo "  SKIP ${name} — ${dst} exists and is not a symlink" >&2
    return 1
  fi

  ln -s "${src}" "${dst}"
  echo "  LINK ${name}  ${dst} -> ${src}"
}

unlink_skill() {
  local name="$1"
  local dst="${GLOBAL_SKILLS_DIR}/${name}"

  if [[ -L "${dst}" ]]; then
    rm "${dst}"
    echo "  UNLINK ${name}  (${dst})"
  else
    echo "  SKIP ${name} — no symlink at ${dst}"
  fi
}

list_skill() {
  local name="$1"
  local dst="${GLOBAL_SKILLS_DIR}/${name}"

  if [[ -L "${dst}" ]]; then
    echo "  ${name}  -> $(readlink "${dst}")"
  else
    echo "  ${name}  (not installed)"
  fi
}

# --- Main ----------------------------------------------------------------

mkdir -p "${GLOBAL_SKILLS_DIR}"

case "${1:-install}" in
  install|"")
    echo "Installing skills globally:"
    for skill in "${SKILLS[@]}"; do
      link_skill "${skill}" || true
    done
    ;;
  --remove|-r|remove|uninstall)
    echo "Removing skill symlinks:"
    for skill in "${SKILLS[@]}"; do
      unlink_skill "${skill}"
    done
    ;;
  --list|-l|list)
    echo "Managed skills:"
    for skill in "${SKILLS[@]}"; do
      list_skill "${skill}"
    done
    ;;
  *)
    echo "Usage: $0 [--install|--remove|--list]" >&2
    exit 1
    ;;
esac
