# install-skills.ps1 — expose project skills and CLI companions globally.
#
# Usage:
#   .\scripts\install-skills.ps1              # install (idempotent)
#   .\scripts\install-skills.ps1 -Remove      # remove junctions and wrappers
#   .\scripts\install-skills.ps1 -List         # list managed junctions and wrappers
#
# Two phases (per ADR-0007, amended by ADR-0008 2026-08-03):
#   1. Skills  — junction .devin\skills\<name> into %APPDATA%\devin\skills\
#   2. CLI     — create wrapper .cmd in %USERPROFILE%\.local\bin\<name> that execs the
#                repo's venv binary. Live edits preserved (repo is canonical).
#
# The CLI phase is required when a skill wraps an external CLI: a skill that
# documents `dcr search ...` is useless if `dcr` is not on PATH.
#
# Junctions (mklink /J) are used instead of symbolic links (mklink /D)
# because junctions do not require Developer Mode or admin privileges on
# Windows. Both are followed by Node.js fs.realpath, which Devin uses.
#
# Legacy cleanup: this script also checks for and removes stale installations
# from the Cascade-era path %USERPROFILE%\.codeium\windsurf\skills\ (per ADR-0008).

param(
  [switch]$Remove,
  [switch]$List
)

# --- Config ---------------------------------------------------------------

# Skills to expose globally (directory names under .devin\skills\).
$Skills = @(
  "dcr-conversation"
)

# CLI binaries to expose globally via wrapper scripts in %USERPROFILE%\.local\bin.
# Format: "<name>:<path-to-repo-binary-relative-to-repo-root>"
# Leave empty for tooling projects that ship pure-procedure skills.
$CliBinaries = @(
  "dcr:.venv\Scripts\dcr.exe"
)

# Global skills directory (XDG-convention Devin path on Windows — per ADR-0008).
$GlobalSkillsDir = Join-Path $env:APPDATA "devin\skills"

# Legacy skills directories (Cascade-era paths — cleaned up during install).
$LegacySkillsDirs = @(
  (Join-Path $env:USERPROFILE ".codeium\windsurf\skills")
)

# Global bin directory for CLI wrappers (standard user PATH location).
$GlobalBinDir = Join-Path $env:USERPROFILE ".local\bin"

# --- Helpers --------------------------------------------------------------

$RepoRoot = Split-Path -Parent $PSScriptRoot

function Link-Skill {
  param([string]$Name)
  $src = Join-Path $RepoRoot ".devin\skills\$Name"
  $dst = Join-Path $GlobalSkillsDir $Name

  if (-not (Test-Path $src -PathType Container)) {
    Write-Host "  SKIP $Name — source not found at $src" -ForegroundColor Yellow
    return
  }

  # Remove existing junction/dir/file at dst.
  if (Test-Path $dst -PathType Container) {
    # Check if it's a reparse point (junction/symlink).
    $item = Get-Item $dst -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
      cmd /c rmdir "$dst" | Out-Null
    } elseif ((Get-ChildItem $dst -Force -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
      Remove-Item $dst -Force
    } else {
      Write-Host "  SKIP $Name — $dst exists and is non-empty" -ForegroundColor Yellow
      return
    }
  } elseif (Test-Path $dst) {
    Write-Host "  SKIP $Name — $dst exists and is not a junction" -ForegroundColor Yellow
    return
  }

  # Create junction (no admin required, unlike symlinks).
  cmd /c mklink /J "$dst" "$src" | Out-Null
  Write-Host "  LINK $Name  $dst -> $src"
}

function Cleanup-Legacy-Skill {
  param([string]$Name)
  foreach ($legacyDir in $LegacySkillsDirs) {
    $legacyDst = Join-Path $legacyDir $Name
    if (Test-Path $legacyDst -PathType Container) {
      $item = Get-Item $legacyDst -Force
      if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        cmd /c rmdir "$legacyDst" | Out-Null
        Write-Host "  CLEANUP legacy $legacyDst (removed stale junction)"
      } elseif ((Get-ChildItem $legacyDst -Force -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
        Remove-Item $legacyDst -Force
        Write-Host "  CLEANUP legacy $legacyDst (removed empty dir)"
      } else {
        Write-Host "  SKIP legacy $legacyDst — non-empty dir, not a junction (remove manually if stale)" -ForegroundColor Yellow
      }
    }
  }
}

function Unlink-Skill {
  param([string]$Name)
  $dst = Join-Path $GlobalSkillsDir $Name

  if (Test-Path $dst -PathType Container) {
    $item = Get-Item $dst -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
      cmd /c rmdir "$dst" | Out-Null
      Write-Host "  UNLINK $Name  ($dst)"
    } else {
      Write-Host "  SKIP $Name — $dst is not a junction"
    }
  } else {
    Write-Host "  SKIP $Name — no junction at $dst"
  }

  # Also clean up legacy paths on -Remove.
  Cleanup-Legacy-Skill $Name
}

function List-Skill {
  param([string]$Name)
  $dst = Join-Path $GlobalSkillsDir $Name

  if (Test-Path $dst -PathType Container) {
    $item = Get-Item $dst -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
      $target = $item.Target
      Write-Host "  $Name  -> $target"
    } else {
      Write-Host "  $Name  (exists but not a junction)"
    }
  } else {
    Write-Host "  $Name  (not installed)"
  }

  # Show legacy installations if they exist.
  foreach ($legacyDir in $LegacySkillsDirs) {
    $legacyDst = Join-Path $legacyDir $Name
    if (Test-Path $legacyDst -PathType Container) {
      $item = Get-Item $legacyDst -Force
      if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        Write-Host "  $Name  -> $($item.Target)  (LEGACY at $legacyDir)"
      } elseif ((Get-ChildItem $legacyDst -Force -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0) {
        Write-Host "  $Name  (LEGACY dir at $legacyDst — non-empty, not a junction)"
      }
    }
  }
}

# Link-Cli <Name> <RelBin>
# Creates a wrapper .cmd at %USERPROFILE%\.local\bin\<Name>.cmd that execs
# the repo's binary. Idempotent: re-running overwrites the wrapper.
function Link-Cli {
  param([string]$Name, [string]$RelBin)
  $bin = Join-Path $RepoRoot $RelBin
  $dst = Join-Path $GlobalBinDir "$Name.cmd"

  if (-not (Test-Path $bin)) {
    Write-Host "  SKIP $Name — binary not found at $bin" -ForegroundColor Yellow
    Write-Host "         (run 'python -m venv .venv; .venv\Scripts\pip install -e .[dev]' first)" -ForegroundColor Yellow
    return
  }

  # Remove existing wrapper (we always rewrite to keep the path current).
  if (Test-Path $dst) {
    Remove-Item $dst -Force
  }

  # .cmd wrapper — uses absolute path to the repo binary, works from any cwd.
  $wrapper = "@echo off`r`nREM Auto-generated by install-skills.ps1 — do not edit.`r`n`"$bin`" %*"
  Set-Content -Path $dst -Value $wrapper -Encoding ASCII
  Write-Host "  WRAP $Name  $dst -> $bin"
}

function Unlink-Cli {
  param([string]$Name)
  $dst = Join-Path $GlobalBinDir "$Name.cmd"

  if (Test-Path $dst) {
    $content = Get-Content $dst -Raw -ErrorAction SilentlyContinue
    if ($content -match "Auto-generated by install-skills.ps1") {
      Remove-Item $dst -Force
      Write-Host "  UNWRAP $Name  ($dst)"
    } else {
      Write-Host "  SKIP $Name — $dst is not an install-skills.ps1 wrapper (left untouched)"
    }
  } else {
    Write-Host "  SKIP $Name — no wrapper at $dst"
  }
}

function List-Cli {
  param([string]$Name)
  $dst = Join-Path $GlobalBinDir "$Name.cmd"

  if (Test-Path $dst) {
    $content = Get-Content $dst -Raw -ErrorAction SilentlyContinue
    if ($content -match "Auto-generated by install-skills.ps1") {
      Write-Host "  $Name  (wrapper at $dst)"
    } else {
      Write-Host "  $Name  (file at $dst is not our wrapper)"
    }
  } else {
    Write-Host "  $Name  (not installed)"
  }
}

# --- Main -----------------------------------------------------------------

if (-not (Test-Path $GlobalSkillsDir)) {
  New-Item -ItemType Directory -Path $GlobalSkillsDir -Force | Out-Null
}
if (-not (Test-Path $GlobalBinDir)) {
  New-Item -ItemType Directory -Path $GlobalBinDir -Force | Out-Null
}

if ($Remove) {
  Write-Host "Removing skill junctions:"
  foreach ($skill in $Skills) { Unlink-Skill $skill }
  if ($CliBinaries.Count -gt 0) {
    Write-Host "Removing CLI wrappers:"
    foreach ($entry in $CliBinaries) {
      $parts = $entry -split ':', 2
      Unlink-Cli $parts[0]
    }
  }
} elseif ($List) {
  Write-Host "Managed skills:"
  foreach ($skill in $Skills) { List-Skill $skill }
  if ($CliBinaries.Count -gt 0) {
    Write-Host "Managed CLI companions:"
    foreach ($entry in $CliBinaries) {
      $parts = $entry -split ':', 2
      List-Cli $parts[0]
    }
  }
} else {
  Write-Host "Installing skills globally:"
  # Clean up legacy installations before installing at the new path.
  foreach ($skill in $Skills) { Cleanup-Legacy-Skill $skill }
  foreach ($skill in $Skills) { Link-Skill $skill }
  if ($CliBinaries.Count -gt 0) {
    Write-Host "Installing CLI companions:"
    foreach ($entry in $CliBinaries) {
      $parts = $entry -split ':', 2
      Link-Cli $parts[0] $parts[1]
    }
  }
  Write-Host ""
  Write-Host "Done. Skills are live (edit SKILL.md in the repo, no re-install)."
  Write-Host "Ensure $GlobalBinDir is on your PATH for CLI companions."
}
