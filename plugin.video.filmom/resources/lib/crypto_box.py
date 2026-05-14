# -*- coding: utf-8 -*-
"""Proteção leve de configuração do FILMOM baseada na senha do cliente.

Este módulo usa apenas biblioteca padrão do Python para manter compatibilidade com
Kodi. O objetivo é impedir que URL, usuário e senha fiquem em texto aberto no
JSON público de distribuição. A chave é derivada da senha digitada pelo cliente.
"""

from __future__ import absolute_import, unicode_literals

import base64
import hashlib
import hmac
import json
import os

ALGORITHM = "filmom-pbkdf2-hmac-xor-v1"
MARKER = "FILMOM_CLIENT_V1"
DEFAULT_ITERATIONS = 160000


def _b64e(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(value):
    value = (value or "").encode("ascii") if isinstance(value, str) else value
    value += b"=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value)


def _json_bytes(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _derive_key(password, salt, iterations):
    password = (password or "").encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", password, salt, int(iterations), dklen=32)


def _keystream(key, nonce, length):
    output = bytearray()
    counter = 0
    while len(output) < length:
        counter_bytes = counter.to_bytes(8, "big")
        output.extend(hmac.new(key, nonce + counter_bytes, hashlib.sha256).digest())
        counter += 1
    return bytes(output[:length])


def _xor_bytes(left, right):
    return bytes(bytearray(a ^ b for a, b in zip(left, right)))


def protect_payload(password, payload, iterations=DEFAULT_ITERATIONS):
    """Retorna um pacote público contendo `payload` protegido pela senha."""
    payload = dict(payload or {})
    payload.setdefault("marker", MARKER)
    salt = os.urandom(16)
    nonce = os.urandom(16)
    key = _derive_key(password, salt, iterations)
    plain = _json_bytes(payload)
    cipher = _xor_bytes(plain, _keystream(key, nonce, len(plain)))
    mac = hmac.new(key, b"FILMOMv1" + nonce + cipher, hashlib.sha256).digest()
    return {
        "algorithm": ALGORITHM,
        "kdf": "pbkdf2_hmac_sha256",
        "iterations": int(iterations),
        "salt": _b64e(salt),
        "nonce": _b64e(nonce),
        "ciphertext": _b64e(cipher),
        "mac": _b64e(mac),
    }


def open_payload(password, box):
    """Abre um pacote protegido. Retorna dict válido ou None se a senha falhar."""
    if not isinstance(box, dict) or box.get("algorithm") != ALGORITHM:
        return None
    try:
        salt = _b64d(box.get("salt", ""))
        nonce = _b64d(box.get("nonce", ""))
        cipher = _b64d(box.get("ciphertext", ""))
        expected_mac = _b64d(box.get("mac", ""))
        iterations = int(box.get("iterations") or DEFAULT_ITERATIONS)
        key = _derive_key(password, salt, iterations)
        actual_mac = hmac.new(key, b"FILMOMv1" + nonce + cipher, hashlib.sha256).digest()
        if not hmac.compare_digest(actual_mac, expected_mac):
            return None
        plain = _xor_bytes(cipher, _keystream(key, nonce, len(cipher)))
        data = json.loads(plain.decode("utf-8"))
        if isinstance(data, dict) and data.get("marker") == MARKER:
            return data
    except Exception:
        return None
    return None
