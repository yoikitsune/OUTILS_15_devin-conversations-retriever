#!/usr/bin/env bash
# install-skills.sh — expose project skills and CLI companions globally.
#
# Usage:
#   ./scripts/install-skills.sh          # install (idempotent)
#   ./scripts/install-skills.sh --remove # remove symlinks and wrappers
#   ./scripts/install-skills.sh --list   # list managed symlinks and wrappers
#
# Two phases (per ADR-0007, amended by ADR-0008 2026-08-03):
#   1. Skills  — symlink .devin/skills/<name> into ~/.config/devin/skills/
#   2. CLI     — create wrapper script in ~/.local/bin/<name> that execs the
#                repo's venv binary. Live edits preserved (repo is canonical).
#
# The CLI phase is required when a skill wraps an external CLI: a skill that
# documents `dcr search ...` is useless if `dcr` is not on PATH. The wrapper
# (not pipx) is used because pipx copies the project into an isolated venv,
# breaking live edits.
#
# Cross-platform: on Windows, run via Git Bash or WSL. For native PowerShell,
# use scripts/install-skills.ps1 (uses junctions, no admin required).
#
# Legacy cleanup: this script also checks for and removes stale installations
# from the Cascade-era path ~/.codeium/windsurf/skills/ (per ADR-0008).

set -euo pipefail

# --- Config --------------------------------------------------------------

# Skills to expose globally (one directory name per line under .devin/skills/).
SKILLS=(
  dcr-conversation
)

# CLI binaries to expose globally via wrapper scripts in ~/.local/bin.
# Format: "<name>:<path-to-repo-binary-relative-to-repo-root>"
# Leave empty for tooling projects that ship pure-procedure skills.
CLI_BINARIES=(
  "dcr:.venv/bin/dcr"
)

# Global skills directory (XDG-convention Devin path — per ADR-0008).
GLOBAL_SKILLS_DIR="${HOME}/.config/devin/skills"

# Legacy skills directories (Cascade-era paths — cleaned up during install).
LEGACY_SKILLS_DIRS=(
  "${HOME}/.codeium/windsurf/skills"
)

# Global bin directory for CLI wrappers (standard user PATH location).
GLOBAL_BIN_DIR="${HOME}/.local/bin"

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

cleanup_legacy_skill() {
  local name="$1"
  for legacy_dir in "${LEGACY_SKILLS_DIRS[@]}"; do
    local legacy_dst="${legacy_dir}/${name}"
    if [[ -L "${legacy_dst}" ]]; then
      rm "${legacy_dst}"
      echo "  CLEANUP legacy ${legacy_dst} (removed stale symlink)"
    elif [[ -d "${legacy_dst}" ]]; then
      if [[ -z "$(ls -A "${legacy_dst}" 2>/dev/null)" ]]; then
        rmdir "${legacy_dst}"
        echo "  CLEANUP legacy ${legacy_dst} (removed empty dir)"
      else
        echo "  SKIP legacy ${legacy_dst} — non-empty dir, not a symlink (remove manually if stale)" >&2
      fi
    fi
  done
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

  # Also clean up legacy paths on --remove.
  cleanup_legacy_skill "${name}"
}

list_skill() {
  local name="$1"
  local dst="${GLOBAL_SKILLS_DIR}/${name}"

  if [[ -L "${dst}" ]]; then
    echo "  ${name}  -> $(readlink "${dst}")"
  else
    echo "  ${name}  (not installed)"
  fi

  # Show legacy installations if they exist.
  for legacy_dir in "${LEGACY_SKILLS_DIRS[@]}"; do
    local legacy_dst="${legacy_dir}/${name}"
    if [[ -L "${legacy_dst}" ]]; then
      echo "  ${name}  -> $(readlink "${legacy_dst}")  (LEGACY at ${legacy_dir})"
    elif [[ -d "${legacy_dst}" && -n "$(ls -A "${legacy_dst}" 2>/dev/null)" ]]; then
      echo "  ${name}  (LEGACY dir at ${legacy_dst} — non-empty, not a symlink)"
    fi
  done
}

# link_cli <name> <repo-relative-path-to-binary>
#
# Creates a wrapper script at ~/.local/bin/<name> that execs the repo's
# binary. The wrapper uses an absolute path to the repo binary, so it works
# regardless of the caller's cwd. Idempotent: re-running overwrites the
# wrapper (e.g., if the repo moved).
link_cli() {
  local name="$1"
  local rel_bin="$2"
  local bin="${repo_root}/${rel_bin}"
  local dst="${GLOBAL_BIN_DIR}/${name}"

  if [[ ! -x "${bin}" ]]; then
    echo "  SKIP ${name} — binary not found or not executable at ${bin}" >&2
    echo "         (run 'python3 -m venv .venv && .venv/bin/pip install -e .[dev]' first)" >&2
    return 1
  fi

  # Remove existing wrapper (we always rewrite to keep the path current).
  if [[ -L "${dst}" || -f "${dst}" ]]; then
    rm "${dst}"
  elif [[ -e "${dst}" ]]; then
    echo "  SKIP ${name} — ${dst} exists and is not a regular file/symlink" >&2
    return 1
  fi

  cat > "${dst}" <<EOF
#!/usr/bin/env bash
# Auto-generated by install-skills.sh — do not edit.
# Wrapper for ${name} (canonical binary in the DCR repo). Live edits: edit
# the repo, no re-install needed. Uninstall: ./scripts/install-skills.sh --remove
exec "${bin}" "\$@"
EOF
  chmod +x "${dst}"
  echo "  WRAP ${name}  ${dst} -> ${bin}"
}

unlink_cli() {
  local name="$1"
  local dst="${GLOBAL_BIN_DIR}/${name}"

  if [[ -f "${dst}" && -r "${dst}" ]]; then
    # Only remove if it's our wrapper (contains the auto-generated marker).
    if grep -q "Auto-generated by install-skills.sh" "${dst}" 2>/dev/null; then
      rm "${dst}"
      echo "  UNWRAP ${name}  (${dst})"
      return
    fi
    echo "  SKIP ${name} — ${dst} is not an install-skills.sh wrapper (left untouched)"
  elif [[ -L "${dst}" ]]; then
    rm "${dst}"
    echo "  UNWRAP ${name}  (${dst} — was a symlink)"
  else
    echo "  SKIP ${name} — no wrapper at ${dst}"
  fi
}

list_cli() {
  local name="$1"
  local dst="${GLOBAL_BIN_DIR}/${name}"

  if [[ -f "${dst}" && -r "${dst}" ]]; then
    if grep -q "Auto-generated by install-skills.sh" "${dst}" 2>/dev/null; then
      local target
      target="$(grep -E '^exec ' "${dst}" | sed -E 's/^exec "([^"]+)".*$/\1/')"
      echo "  ${name}  -> ${target}  (wrapper)"
    else
      echo "  ${name}  (file at ${dst} is not our wrapper)"
    fi
  else
    echo "  ${name}  (not installed)"
  fi
}

# --- Main ----------------------------------------------------------------

mkdir -p "${GLOBAL_SKILLS_DIR}" "${GLOBAL_BIN_DIR}"

case "${1:-install}" in
  install|"")
    echo "Installing skills globally:"
    # Clean up legacy installations before installing at the new path.
    for skill in "${SKILLS[@]}"; do
      cleanup_legacy_skill "${skill}" || true
    done
    for skill in "${SKILLS[@]}"; do
      link_skill "${skill}" || true
    done
    if [[ ${#CLI_BINARIES[@]} -gt 0 ]]; then
      echo "Installing CLI companions:"
      for entry in "${CLI_BINARIES[@]}"; do
        name="${entry%%:*}"
        rel_bin="${entry#*:}"
        link_cli "${name}" "${rel_bin}" || true
      done
    fi
    echo ""
    echo "Done. Skills are live (edit SKILL.md in the repo, no re-install)."
    echo "Ensure ${GLOBAL_BIN_DIR} is on your PATH for CLI companions."
    ;;
  --remove|-r|remove|uninstall)
    echo "Removing skill symlinks:"
    for skill in "${SKILLS[@]}"; do
      unlink_skill "${skill}"
    done
    if [[ ${#CLI_BINARIES[@]} -gt 0 ]]; then
      echo "Removing CLI wrappers:"
      for entry in "${CLI_BINARIES[@]}"; do
        name="${entry%%:*}"
        unlink_cli "${name}"
      done
    fi
    ;;
  --list|-l|list)
    echo "Managed skills:"
    for skill in "${SKILLS[@]}"; do
      list_skill "${skill}"
    done
    if [[ ${#CLI_BINARIES[@]} -gt 0 ]]; then
      echo "Managed CLI companions:"
      for entry in "${CLI_BINARIES[@]}"; do
        name="${entry%%:*}"
        list_cli "${name}"
      done
    fi
    ;;
  *)
    echo "Usage: $0 [--install|--remove|--list]" >&2
    exit 1
    ;;
esac
