"""Bounded-memory exact-overlap candidate selection, not duplicate adjudication.

Pure functions only: no real-data reader, persistence, model, or gate release.
Fingerprints select candidates; callers MUST verify original measurement values.
"""
from collections import deque
import hashlib
import math
import struct

K = 8
WINDOW = 25
GUARANTEED_LENGTH = K + WINDOW - 1


def measurement_token(key, values):
    """Common 8-column projection: status/time/V/I/Q, excluding identity.

    Optional energy is deliberately excluded for cross-layout comparison.
    Exact decoded numeric equality only; no tolerance or rounding. Negative
    zero is normalized. Time is the already validated integer microsecond key.
    """
    if (not isinstance(key, (tuple, list)) or len(key) != 5
            or any(type(v) is not int for v in key)
            or key[4] < 0 or not -(2**63) <= key[2] < 2**63
            or not key[4] < 2**63):
        raise ValueError("invalid record metadata key")
    if len(values) not in (8, 9):
        raise ValueError("invalid record width")
    numbers = values[5:8]
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in numbers):
        raise ValueError("invalid measurement")
    return struct.pack(">qqddd", key[2], key[4], *(0.0 if v == 0 else v for v in numbers))


def shingles(tokens, k=K):
    """Every length-k contiguous shingle, with zero-based candidate offset."""
    if type(k) is not int or k < 1:
        raise ValueError("invalid shingle length")
    recent = deque(maxlen=k)
    for offset, token in enumerate(tokens):
        if not isinstance(token, bytes) or len(token) != 40:
            raise ValueError("invalid canonical token")
        recent.append(token)
        if len(recent) == k:
            yield offset-k+1, hashlib.sha256(b"".join(recent)).digest()


def winnow(tokens, k=K, window=WINDOW):
    """Rightmost minimum for each full window of shingle hashes.

    Memory O(k+window), preserves chunk/worksheet boundaries if caller supplies
    one continuous iterator per candidate. No padding of short candidates.
    """
    if type(window) is not int or window < 1:
        raise ValueError("invalid fingerprint window")
    minima = deque()
    emitted = None
    for offset, digest in shingles(tokens, k):
        while minima and minima[-1][1] >= digest:
            minima.pop()
        minima.append((offset, digest))
        while minima[0][0] <= offset-window:
            minima.popleft()
        if offset >= window-1 and minima[0][0] != emitted:
            emitted = minima[0][0]
            yield minima[0]


def reference_winnow(tokens, k=K, window=WINDOW):
    """Small synthetic oracle; never materialize a real fleet through this."""
    if type(k) is not int or k < 1 or type(window) is not int or window < 1:
        raise ValueError("invalid fingerprint parameters")
    values = list(tokens)
    if any(not isinstance(t, bytes) or len(t) != 40 for t in values):
        raise ValueError("invalid canonical token")
    hashes = [hashlib.sha256(b"".join(values[i:i+k])).digest()
              for i in range(len(values)-k+1)]
    result = []
    for start in range(len(hashes)-window+1):
        index = min(range(start, start+window), key=lambda i: (hashes[i], -i))
        if not result or result[-1][0] != index:
            result.append((index, hashes[index]))
    return result


def confirm_projection(left, right, minimum=GUARANTEED_LENGTH):
    """Confirm equal finite-length canonical sequences, never hash equality.

    This only confirms the common measurement projection, not optional energy,
    device identity, near duplicates, or physical independence.
    """
    if type(minimum) is not int or minimum < 1:
        raise ValueError("invalid minimum")
    from itertools import zip_longest
    missing = object()
    count = 0
    for a, b in zip_longest(left, right, fillvalue=missing):
        if a is missing or b is missing:
            return False
        if not isinstance(a, bytes) or len(a) != 40 or not isinstance(b, bytes) or len(b) != 40:
            raise ValueError("invalid canonical token")
        if a != b:
            return False
        count += 1
    return count >= minimum
