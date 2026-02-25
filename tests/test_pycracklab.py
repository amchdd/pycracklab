"""
tests/test_pycracklab.py
========================
Testes unitários para PyCrackLab.
Execute com: pytest tests/ -v
"""

import hashlib
import sys
import os

# Adiciona raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import bcrypt

from utils.hashing import (
    hash_md5,
    hash_sha1,
    hash_sha256,
    detect_hash_type,
    generate_hash,
)
from cracker.brute import (
    get_charset,
    estimate_combinations,
    candidate_generator,
    BruteForceAttack,
)
from cracker.wordlist import check_candidate, wordlist_generator
from cracker.hash_cracker import validate_hash, HashCracker


# ─────────────────────────────────────────────
# utils/hashing.py
# ─────────────────────────────────────────────

class TestHashing:
    def test_md5_known_value(self):
        """MD5 de 'hello' deve ser o valor canônico."""
        assert hash_md5("hello") == "5d41402abc4b2a76b9719d911017c592"

    def test_sha1_known_value(self):
        """SHA1 de 'hello' deve ser o valor canônico."""
        assert hash_sha1("hello") == "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"

    def test_sha256_known_value(self):
        result = hash_sha256("hello")
        assert len(result) == 64
        assert result == hashlib.sha256(b"hello").hexdigest()

    def test_md5_empty_string(self):
        assert hash_md5("") == "d41d8cd98f00b204e9800998ecf8427e"

    def test_sha1_unicode(self):
        """Deve lidar com caracteres UTF-8."""
        result = hash_sha1("são paulo")
        assert len(result) == 40
        assert all(c in "0123456789abcdef" for c in result)

    def test_detect_hash_type_md5(self):
        assert detect_hash_type("5d41402abc4b2a76b9719d911017c592") == "md5"

    def test_detect_hash_type_sha1(self):
        assert detect_hash_type("aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d") == "sha1"

    def test_detect_hash_type_sha256(self):
        h = "a" * 64
        assert detect_hash_type(h) == "sha256"

    def test_detect_hash_type_bcrypt(self):
        salt = bcrypt.gensalt(rounds=4)
        hashed = bcrypt.hashpw(b"test", salt).decode()
        assert detect_hash_type(hashed) == "bcrypt"

    def test_detect_hash_type_unknown(self):
        assert detect_hash_type("notatallahash") is None
        assert detect_hash_type("abc123") is None

    def test_detect_hash_type_case_insensitive(self):
        """MD5 em maiúsculas deve ser detectado."""
        upper_md5 = "5D41402ABC4B2A76B9719D911017C592"
        assert detect_hash_type(upper_md5) == "md5"

    def test_generate_hash_md5(self):
        assert generate_hash("test", "md5") == hash_md5("test")

    def test_generate_hash_sha1(self):
        assert generate_hash("test", "sha1") == hash_sha1("test")

    def test_generate_hash_bcrypt(self):
        result = generate_hash("test", "bcrypt")
        assert result.startswith("$2b$")
        assert bcrypt.checkpw(b"test", result.encode())

    def test_generate_hash_unsupported(self):
        with pytest.raises(ValueError, match="não suportado"):
            generate_hash("test", "sha9999")


# ─────────────────────────────────────────────
# cracker/brute.py
# ─────────────────────────────────────────────

class TestBruteForce:
    def test_get_charset_lowercase(self):
        charset = get_charset("lowercase")
        assert charset == "abcdefghijklmnopqrstuvwxyz"
        assert len(charset) == 26

    def test_get_charset_digits(self):
        charset = get_charset("digits")
        assert charset == "0123456789"

    def test_get_charset_custom(self):
        charset = get_charset("lowercase", custom_charset="abc123")
        assert charset == "abc123"

    def test_get_charset_custom_deduplication(self):
        charset = get_charset("lowercase", custom_charset="aaabbbccc")
        assert charset == "abc"

    def test_estimate_combinations_single_char(self):
        # charset=2, len 1-1: 2^1 = 2
        assert estimate_combinations("ab", 1, 1) == 2

    def test_estimate_combinations_range(self):
        # charset=2, len 1-2: 2 + 4 = 6
        assert estimate_combinations("ab", 1, 2) == 6

    def test_candidate_generator_order(self):
        """Deve gerar candidatos em ordem (menor para maior)."""
        candidates = list(candidate_generator("ab", 1, 2))
        assert candidates[:2] == ["a", "b"]  # len=1
        assert len(candidates) == 6  # 2 + 4

    def test_brute_force_finds_target(self):
        """Deve encontrar 'b' em charset 'abc', len 1."""
        attack = BruteForceAttack(target="b", charset_name="lowercase",
                                  custom_charset="abc", min_len=1, max_len=1)
        result = attack.run()
        assert result == "b"

    def test_brute_force_finds_two_chars(self):
        """Deve encontrar 'ca' em charset 'abc', len 2."""
        attack = BruteForceAttack(target="ca", charset_name="lowercase",
                                  custom_charset="abc", min_len=2, max_len=2)
        result = attack.run()
        assert result == "ca"

    def test_brute_force_not_found(self):
        """Deve retornar None se alvo não está no espaço de busca."""
        attack = BruteForceAttack(target="z", charset_name="lowercase",
                                  custom_charset="abc", min_len=1, max_len=1)
        result = attack.run()
        assert result is None

    def test_brute_force_invalid_target(self):
        with pytest.raises(ValueError):
            BruteForceAttack(target="", charset_name="lowercase")

    def test_brute_force_invalid_lengths(self):
        with pytest.raises(ValueError):
            BruteForceAttack(target="a", min_len=5, max_len=2)

    def test_brute_force_multithreaded(self):
        """Deve encontrar resultado com múltiplas threads."""
        attack = BruteForceAttack(target="b", charset_name="lowercase",
                                  custom_charset="abc", min_len=1, max_len=1,
                                  num_threads=2)
        result = attack.run()
        assert result == "b"


# ─────────────────────────────────────────────
# cracker/wordlist.py
# ─────────────────────────────────────────────

class TestWordlistChecker:
    def test_check_md5_correct(self):
        md5 = hash_md5("password")
        assert check_candidate("password", md5, "md5") is True

    def test_check_md5_wrong(self):
        md5 = hash_md5("password")
        assert check_candidate("wrong", md5, "md5") is False

    def test_check_sha1_correct(self):
        sha1 = hash_sha1("hello123")
        assert check_candidate("hello123", sha1, "sha1") is True

    def test_check_sha1_wrong(self):
        sha1 = hash_sha1("hello123")
        assert check_candidate("nope", sha1, "sha1") is False

    def test_check_bcrypt_correct(self):
        hashed = bcrypt.hashpw(b"mypass", bcrypt.gensalt(rounds=4)).decode()
        assert check_candidate("mypass", hashed, "bcrypt") is True

    def test_check_bcrypt_wrong(self):
        hashed = bcrypt.hashpw(b"mypass", bcrypt.gensalt(rounds=4)).decode()
        assert check_candidate("wrongpass", hashed, "bcrypt") is False

    def test_check_case_sensitivity_md5(self):
        """Hash em maiúsculas deve ser aceito."""
        md5_upper = hash_md5("test").upper()
        assert check_candidate("test", md5_upper, "md5") is True

    def test_wordlist_generator(self, tmp_path):
        """Deve ler arquivo e ignorar linhas vazias."""
        wl = tmp_path / "test.txt"
        wl.write_text("password\n\n123456\n  \ntest\n")
        words = list(wordlist_generator(str(wl)))
        assert words == ["password", "123456", "test"]

    def test_wordlist_generator_missing_file(self):
        with pytest.raises(FileNotFoundError):
            list(wordlist_generator("/tmp/does_not_exist_xyz.txt"))


# ─────────────────────────────────────────────
# cracker/hash_cracker.py
# ─────────────────────────────────────────────

class TestHashValidation:
    def test_validate_md5(self):
        is_valid, htype = validate_hash("5d41402abc4b2a76b9719d911017c592")
        assert is_valid is True
        assert htype == "md5"

    def test_validate_sha1(self):
        is_valid, htype = validate_hash("aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d")
        assert is_valid is True
        assert htype == "sha1"

    def test_validate_bcrypt(self):
        hashed = bcrypt.hashpw(b"x", bcrypt.gensalt(rounds=4)).decode()
        is_valid, htype = validate_hash(hashed)
        assert is_valid is True
        assert htype == "bcrypt"

    def test_validate_invalid(self):
        is_valid, htype = validate_hash("notahash")
        assert is_valid is False
        assert htype == ""

    def test_hash_cracker_invalid_hash(self):
        with pytest.raises(ValueError):
            HashCracker(hash_value="notahash", wordlist_path="/any")

    def test_hash_cracker_detects_md5(self, tmp_path):
        """HashCracker deve detectar MD5 e encontrar senha na wordlist."""
        wl = tmp_path / "wl.txt"
        wl.write_text("wrongpass\nhello\nanotherpass\n")
        md5 = hash_md5("hello")
        cracker = HashCracker(hash_value=md5, wordlist_path=str(wl))
        assert cracker.hash_type == "md5"
        result = cracker.run()
        assert result == "hello"


# ─────────────────────────────────────────────
# Testes de integração
# ─────────────────────────────────────────────

class TestIntegration:
    def test_full_md5_crack_flow(self, tmp_path):
        """Fluxo completo: gerar hash → atacar → encontrar senha."""
        password = "hunter2"
        md5_hash = hash_md5(password)

        wl = tmp_path / "rockyou_mock.txt"
        wl.write_text("\n".join([
            "dragon", "password", "123456", "hunter2", "qwerty"
        ]))

        cracker = HashCracker(hash_value=md5_hash, wordlist_path=str(wl))
        result = cracker.run()
        assert result == password

    def test_full_sha1_crack_flow(self, tmp_path):
        """Fluxo completo para SHA1."""
        password = "letmein"
        sha1_hash = hash_sha1(password)

        wl = tmp_path / "wl.txt"
        wl.write_text("\n".join(["abc", "letmein", "xyz"]))

        from cracker.wordlist import WordlistAttack
        attack = WordlistAttack(hash_value=sha1_hash, wordlist_path=str(wl), hash_type="sha1")
        result = attack.run()
        assert result == password
