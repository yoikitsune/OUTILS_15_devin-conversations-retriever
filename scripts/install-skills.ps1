# install-skills.ps1 — expose project skills globally via directory junctions.
#
# Usage:
#   .\scripts\install-skills.ps1              # install (idempotent)
#   .\scripts\install-skills.ps1 -Remove      # remove junctions
#   .\scripts\install-skills.ps1 -List         # list managed junctions
#
# Skills are junctioned from .devin/skills/<name> into the global Windsurf
# skills directory (%USERPROFILE%\.codeium\windsurf\skills\<name>). Edits
# in the repo are live — no re-install needed.
#
# Junctions (mklink /J) are used instead of symbolic links (mklink /D)
# because junctions do not require Developer Mode or admin privileges on
# Windows. Both are followed by Node.js fs.realpath, which Devin uses.

param(
  [switch]$Remove,
  [switch]$List
)

# --- Config ---------------------------------------------------------------

# Skills to expose globally (directory names under .devin/skills/).
$Skills = @(
  "dcr-conversation"
)

# Global skills directory (Windsurf channel — read by Devin via import).
$GlobalSkillsDir = Join-Path $env:USERPROFILE ".codeium\windsurf\skills"

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
}

# --- Main -----------------------------------------------------------------

if (-not (Test-Path $GlobalSkillsDir)) {
  New-Item -ItemType Directory -Path $GlobalSkillsDir -Force | Out-Null
}

if ($Remove) {
  Write-Host "Removing skill junctions:"
  foreach ($skill in $Skills) { Unlink-Skill $skill }
} elseif ($List) {
  Write-Host "Managed skills:"
  foreach ($skill in $Skills) { List-Skill $skill }
} else {
  Write-Host "Installing skills globally:"
  foreach ($skill in $Skills) { Link-Skill $skill }
}
