"""Disk-backed candidate search and bounded exact confirmation helpers.

No real-data CLI/release. A caller must supply trusted position-mapped reads,
fully consume pair enumeration, and independently reconcile coverage/results.
"""
import math
from pathlib import Path
import sqlite3

if __package__:
    from experiments.audit_cap.ren_overlap import K, GUARANTEED_LENGTH
else:
    from ren_overlap import K, GUARANTEED_LENGTH


class DiskIndex:
    """New local-only SQLite index, one atomic insert transaction per group.

    Existing paths are never replaced. Failed groups roll back; callers must
    still record the failure and cannot claim completion of the planned fleet.
    """
    def __init__(self, path):
        path = Path(path)
        with path.open("xb"):
            pass
        self.db = sqlite3.connect(path)
        try:
            self.db.execute("PRAGMA cache_size=-8192")
            self.db.execute("PRAGMA temp_store=FILE")
            self.db.executescript("""
                CREATE TABLE groups (gid INTEGER PRIMARY KEY, rows INTEGER NOT NULL);
                CREATE TABLE fingerprints (digest BLOB NOT NULL, gid INTEGER NOT NULL,
                    offset INTEGER NOT NULL, PRIMARY KEY(gid,offset));
                CREATE INDEX digest_lookup ON fingerprints(digest,gid,offset);
            """)
        except BaseException:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def add(self, gid, rows, fingerprints):
        if type(gid) is not int or gid < 0 or type(rows) is not int or rows < 0:
            raise ValueError("invalid group metadata")
        previous = -1
        with self.db:
            self.db.execute("INSERT INTO groups VALUES (?,?)", (gid, rows))
            for offset, digest in fingerprints:
                if (type(offset) is not int or not previous < offset <= rows-K
                        or type(digest) is not bytes or len(digest) != 32):
                    raise ValueError("invalid fingerprint position/value")
                self.db.execute("INSERT INTO fingerprints VALUES (?,?,?)", (digest,gid,offset))
                previous = offset
            if rows >= GUARANTEED_LENGTH and previous == -1:
                raise ValueError("missing fingerprints for eligible-length group")

    def pairs(self):
        """Yield all cross-group equal-hash positions; no cap or dedup heuristic.

        Caller must not mutate this index while consuming. Repeated fragments
        may create quadratic output; do not turn early stopping into a PASS.
        """
        cursor = self.db.execute("""
            SELECT a.gid,a.offset,b.gid,b.offset
            FROM fingerprints a JOIN fingerprints b
              ON a.digest=b.digest AND a.gid<b.gid
        """)
        try:
            yield from cursor
        finally:
            cursor.close()


def confirm_anchor(read_left, read_right, left_rows, right_rows, left, right):
    """Confirm a candidate in bounded decoded-value context around an 8-row seed.

    Each read(offset) returns (40-byte canonical token, optional finite energy).
    At most 24 rows on each side are examined: enough to find any exact32 match
    containing this seed, not enough to report the maximal duplicate length.
    Returned interval is half-open and is a confirmed projected span only.
    """
    if any(type(v) is not int for v in (left_rows,right_rows,left,right)):
        raise ValueError("noninteger position")
    if not 0 <= left <= left_rows-K or not 0 <= right <= right_rows-K:
        raise ValueError("anchor out of bounds")

    def pair(a, b):
        values = []
        for read, offset in ((read_left,a),(read_right,b)):
            token, energy = read(offset)
            if not isinstance(token,bytes) or len(token)!=40:
                raise ValueError("invalid readback token")
            if energy is not None and (type(energy) not in (int,float) or not math.isfinite(energy)):
                raise ValueError("invalid readback energy")
            values.append((token,energy))
        return values

    def equal(a,b):
        x,y = pair(a,b)
        return x[0]==y[0]

    for shift in range(K):
        if not equal(left+shift,right+shift):
            return None  # A hash candidate alone never confirms even the seed.
    before=after=0
    for shift in range(1,GUARANTEED_LENGTH-K+1):
        if left-shift<0 or right-shift<0 or not equal(left-shift,right-shift):
            break
        before=shift
    for shift in range(GUARANTEED_LENGTH-K):
        a,b=left+K+shift,right+K+shift
        if a>=left_rows or b>=right_rows or not equal(a,b):
            break
        after=shift+1
    length=before+K+after
    if length<GUARANTEED_LENGTH:
        return None
    compared=missing=mismatches=0
    # Recheck whole returned span independently of boundary extension decisions.
    for shift in range(-before,K+after):
        x,y=pair(left+shift,right+shift)
        if x[0]!=y[0]:
            raise ValueError("readback changed during confirmation")
        if x[1] is None or y[1] is None:
            missing+=1
        else:
            compared+=1
            mismatches+=int(x[1]!=y[1])
    return dict(left_start=left-before,right_start=right-before,length=length,
        energy_compared_rows=compared,energy_missing_rows=missing,
        energy_mismatch_rows=mismatches,maximal_extent_verified=False,
        physical_identity_verified=False)


def source_position(spans, offset):
    """Map a group offset through ordered (member,sheet_index,name,row_count)."""
    if type(offset) is not int or offset<0:
        raise ValueError("invalid offset")
    remaining=offset
    for member,index,name,rows in spans:
        if type(rows) is not int or rows<1:
            raise ValueError("invalid span")
        if remaining<rows:
            return member,index,name,remaining+2
        remaining-=rows
    raise ValueError("offset outside group")
