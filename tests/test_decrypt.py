"""Tests for dcr.decrypt module."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from dcr.decrypt import KEY, NONCE_SIZE, TAG_SIZE, decrypt_bytes, decrypt_file, decrypt_batch


# --- Fixtures ---

@pytest.fixture
def sample_plaintext() -> bytes:
    """Fake protobuf-like plaintext for testing."""
    return b"\x0a\x04test\x12\x08abcdefgh"


@pytest.fixture
def encrypted_pb(tmp_path: Path, sample_plaintext: bytes) -> Path:
    """Create a valid encrypted .pb file in tmp_path."""
    nonce = b"\x01" * NONCE_SIZE
    ct_and_tag = AESGCM(KEY).encrypt(nonce, sample_plaintext, None)
    pb_path = tmp_path / "test.pb"
    pb_path.write_bytes(nonce + ct_and_tag)
    return pb_path


@pytest.fixture
def encrypted_dir(tmp_path: Path, sample_plaintext: bytes) -> Path:
    """Create a directory with multiple encrypted .pb files."""
    in_dir = tmp_path / "input"
    in_dir.mkdir()
    for i in range(3):
        nonce = bytes([i + 1]) * NONCE_SIZE
        ct_and_tag = AESGCM(KEY).encrypt(nonce, sample_plaintext, None)
        (in_dir / f"conv{i}.pb").write_bytes(nonce + ct_and_tag)
    return in_dir


# --- Nominal tests ---

def test_decrypt_bytes_valid(sample_plaintext: bytes, encrypted_pb: Path):
    """Decrypting valid encrypted bytes returns original plaintext."""
    data = encrypted_pb.read_bytes()
    result = decrypt_bytes(data)
    assert result == sample_plaintext


def test_decrypt_file_valid(sample_plaintext: bytes, encrypted_pb: Path):
    """Decrypting a valid .pb file returns original plaintext."""
    result = decrypt_file(encrypted_pb)
    assert result == sample_plaintext


def test_decrypt_batch_all_ok(encrypted_dir: Path, tmp_path: Path, sample_plaintext: bytes):
    """Batch decryption succeeds for all valid files."""
    out_dir = tmp_path / "output"
    ok, fail, errors = decrypt_batch(encrypted_dir, out_dir)
    assert ok == 3
    assert fail == 0
    assert errors == []
    for i in range(3):
        assert (out_dir / f"conv{i}.bin").read_bytes() == sample_plaintext


def test_decrypt_batch_no_output_dir(encrypted_dir: Path):
    """Batch decryption works without writing output."""
    ok, fail, errors = decrypt_batch(encrypted_dir)
    assert ok == 3
    assert fail == 0


def test_key_is_32_bytes():
    """AES-256 key must be 32 bytes."""
    assert len(KEY) == 32


# --- Error tests ---

def test_decrypt_bytes_too_small():
    """Decrypting data smaller than nonce + tag raises ValueError."""
    with pytest.raises(ValueError, match="too small"):
        decrypt_bytes(b"\x00" * 10)


def test_decrypt_file_not_found(tmp_path: Path):
    """Decrypting a non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        decrypt_file(tmp_path / "nonexistent.pb")


def test_decrypt_bytes_wrong_key():
    """Decrypting with wrong key raises InvalidTag."""
    nonce = b"\x02" * NONCE_SIZE
    wrong_key = b"0" * 32
    ct_and_tag = AESGCM(wrong_key).encrypt(nonce, b"secret", None)
    with pytest.raises(Exception):
        decrypt_bytes(nonce + ct_and_tag)


def test_decrypt_bytes_corrupted(encrypted_pb: Path):
    """Decrypting corrupted data raises InvalidTag."""
    data = bytearray(encrypted_pb.read_bytes())
    data[-1] ^= 0xFF  # flip a bit in the tag
    with pytest.raises(Exception):
        decrypt_bytes(bytes(data))


def test_decrypt_batch_mixed(encrypted_dir: Path, tmp_path: Path):
    """Batch decryption with one corrupt file reports partial failure."""
    # Corrupt one file
    bad_file = encrypted_dir / "conv1.pb"
    data = bytearray(bad_file.read_bytes())
    data[-1] ^= 0xFF
    bad_file.write_bytes(bytes(data))

    out_dir = tmp_path / "output"
    ok, fail, errors = decrypt_batch(encrypted_dir, out_dir)
    assert ok == 2
    assert fail == 1
    assert len(errors) == 1
    assert "conv1.pb" in errors[0]
