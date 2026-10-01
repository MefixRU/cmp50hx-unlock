#!/usr/bin/env python3
"""Persistently patch NVIDIA 610.43.03 libcuda for mixed-generation P2P support."""

from pathlib import Path
import re
import sys

PATCHES = (
    (
        "can-access predicate",
        """
        48 8b 83 50 0c 00 00
        49 8b 94 24 50 0c 00 00
        48 39 d0
        74 ??
        48 3d c0 00 00 00
        75 ??
        48 81 fa c8 00 00 00
        74 ??
        48 3d c8 00 00 00
        75 ??
        48 81 fa c0 00 00 00
        74 ??
        83 e0 f0
        48 3d f0 00 00 00
        74 ??
        31 c0
        """,
        (18, b"\xeb"),
    ),
    (
        "compatibility predicate",
        """
        48 8b 87 50 0c 00 00
        48 8b 93 50 0c 00 00
        48 39 d0
        74 ??
        48 3d c0 00 00 00
        75 ??
        48 81 fa c8 00 00 00
        74 ??
        48 3d c8 00 00 00
        75 ??
        48 81 fa c0 00 00 00
        74 ??
        83 e0 f0
        48 3d f0 00 00 00
        75 ??
        83 e2 f0
        """,
        (17, b"\xeb"),
    ),
    (
        "peer-device selection",
        """
        49 8b 87 50 0c 00 00  # mov rax, [r15+0xc50]
        49 8b 96 50 0c 00 00  # mov rdx, [r14+0xc50]
        48 39 d0              # cmp rax, rdx
        0f 84 87 00 00 00     # je (near) -> jmp (near) + nop
        48 81 fa c8 00 00 00  # cmp rdx, 0xc8
        75 08                 # jne
        48 3d c0 00 00 00     # cmp rax, 0xc0
        74 76                 # je
        48 81 fa c0 00 00 00  # cmp rdx, 0xc0
        75 08                 # jne
        48 3d c8 00 00 00     # cmp rax, 0xc8
        74 65                 # je
        83 e0 f0              # and eax, -0x10
        48 3d f0 00 00 00     # cmp rax, 0xf0
        74 4e                 # je  ← конец сигнатуры
        """,
        (17, b"\xe9\x88\x00\x00\x00\x90"),
    ),
    (
        "peer setup",
        """
        49 8b 84 24 50 0c 00 00
        49 8b 95 50 0c 00 00
        48 39 d0
        74 6a
        48 3d c0 00 00 00
        75 09
        48 81 fa c8 00 00 00
        74 59
        48 81 fa c0 00 00 00
        75 08
        48 3d c8 00 00 00
        74 48
        83 e0 f0
        48 3d f0 00 00 00
        75 15
        83 e2 f0
        48 81 fa f0 00 00 00
        74 31
        """,
        (18, b"\xeb"),
    ),
)


def parse_signature(sig: str):
    """Возвращает (pattern_bytes, wildcard_mask) — по одному байту на токен."""
    tokens = re.sub(r"#.*", "", sig).split()
    pattern = bytearray()
    mask = bytearray()
    for t in tokens:
        if t == "??":
            pattern.append(0)
            mask.append(1)
        else:
            pattern.append(bytes.fromhex(t)[0])
            mask.append(0)
    return bytes(pattern), bytes(mask)


def find_all(data: bytes, pattern: bytes, mask: bytes):
    """Ручной поиск с wildcard-маской. Быстрый за счёт bytes.find()."""
    n = len(pattern)
    # Ищем самую длинную непрерывную последовательность точных байтов
    best_start = best_len = cur_start = cur_len = 0
    for i in range(n):
        if mask[i] == 0:
            if cur_len == 0:
                cur_start = i
            cur_len += 1
            if cur_len > best_len:
                best_start, best_len = cur_start, cur_len
        else:
            cur_len = 0

    if best_len < 4:
        # слишком короткая якорная последовательность — линейный поиск
        results = []
        for i in range(len(data) - n + 1):
            ok = True
            for j in range(n):
                if mask[j] == 0 and data[i + j] != pattern[j]:
                    ok = False
                    break
            if ok:
                results.append(i)
        return results

    needle = pattern[best_start:best_start + best_len]
    results = []
    start = 0
    while True:
        idx = data.find(needle, start)
        if idx == -1:
            break
        cand = idx - best_start
        if 0 <= cand <= len(data) - n:
            ok = True
            for j in range(n):
                if mask[j] == 0 and data[cand + j] != pattern[j]:
                    ok = False
                    break
            if ok:
                results.append(cand)
        start = idx + 1
    return results


if len(sys.argv) != 2:
    raise SystemExit(f"usage: {sys.argv[0]} LIBCUDA")

source = Path(sys.argv[1])
data = bytearray(source.read_bytes())
changes = []

for name, sig, (branch_off, replacement) in PATCHES:
    pattern, mask = parse_signature(sig)
    matches = find_all(bytes(data), pattern, mask)
    if len(matches) != 1:
        raise SystemExit(f"error: {name} signature matched {len(matches)} times instead of once")
    off = matches[0] + branch_off
    data[off:off + len(replacement)] = replacement
    changes.append((name, off, replacement))

source.write_bytes(data)
for name, off, _ in changes:
    print(f"applied: {name} at 0x{off:x}")