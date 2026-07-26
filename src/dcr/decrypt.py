"""AES-256-GCM decryption for Windsurf Cascade .pb trajectory files.

Adapted from dayearleo/windsurf-local-user-data-decryption (MIT).
See ADR-0003 for reuse rationale.

File layout: [12-byte nonce][ciphertext][16-byte GCM tag]
Key: hardcoded global constant shared across all Windsurf users.
"""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY: bytes = b"safeCodeiumworldKeYsecretBalloon"
assert len(KEY) == 32, "AES-256 key must be 32 bytes"

NONCE_SIZE = 12
TAG_SIZE = 16


def decrypt_bytes(data: bytes) -> bytes:
    """Decrypt raw .pb file bytes.

    Args:
        data: Raw encrypted bytes from a .pb file (nonce + ciphertext + tag).

    Returns:
        Decrypted plaintext (protobuf-encoded CortexTrajectory).

    Raises:
        ValueError: If data is too small to contain nonce + tag.
        cryptography.exceptions.InvalidTag: If decryption fails (wrong key / corrupted data).
    """
    if len(data) < NONCE_SIZE + TAG_SIZE:
        raise ValueError(
            f"Data too small: {len(data)} bytes, need at least {NONCE_SIZE + TAG_SIZE}"
        )
    nonce = data[:NONCE_SIZE]
    ct_and_tag = data[NONCE_SIZE:]
    return AESGCM(KEY).decrypt(nonce, ct_and_tag, None)


def decrypt_file(pb_path: Path) -> bytes:
    """Decrypt a .pb file on disk.

    Args:
        pb_path: Path to the encrypted .pb file.

    Returns:
        Decrypted plaintext bytes.

    Raises:
        FileNotFoundError: If pb_path does not exist.
        ValueError: If file is too small.
        cryptography.exceptions.InvalidTag: If decryption fails.
    """
    return decrypt_bytes(pb_path.read_bytes())


def decrypt_batch(
    input_dir: Path,
    output_dir: Path | None = None,
) -> tuple[int, int, list[str]]:
    """Decrypt all .pb files in a directory.

    Args:
        input_dir: Directory containing .pb files.
        output_dir: If provided, write decrypted .bin files here.
            If None, decrypted data is not written to disk.

    Returns:
        Tuple of (success_count, failure_count, list_of_error_messages).
    """
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    fail = 0
    errors: list[str] = []

    for src in sorted(input_dir.glob("*.pb")):
        try:
            pt = decrypt_file(src)
            if output_dir is not None:
                dst = output_dir / (src.stem + ".bin")
                dst.write_bytes(pt)
            ok += 1
        except Exception as exc:
            fail += 1
            errors.append(f"{src.name}: {exc}")

    return ok, fail, errors
