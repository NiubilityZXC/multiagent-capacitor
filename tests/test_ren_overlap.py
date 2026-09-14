import random
import pytest
from experiments.audit_cap import ren_overlap as o


def token(i):
    return o.measurement_token((1, 1, 0, i, i*1000), [1, 1, 0, i, "", i/100, -20., i/1000])


def test_projection_excludes_identifiers_and_optional_energy():
    a = o.measurement_token((1, 2, 0, 3, 4000), [1, 2, 0, 3, "", 1., -20., .5])
    b = o.measurement_token((9, 8, 0, 7, 4000), [9, 8, 0, 7, "", 1., -20., .5, 3.])
    assert a == b
    assert len(a) == 40


def test_signed_zero_and_no_rounding():
    key = (1, 2, 0, 3, 0)
    values = [1, 2, 0, 3, "", 0., 0., 0.]
    assert o.measurement_token(key, values) == o.measurement_token(key, values[:5]+[-0., -0., -0.])
    assert o.measurement_token(key, values) != o.measurement_token(key, values[:5]+[1e-12, 0., 0.])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "1", None])
def test_invalid_measurement(value):
    with pytest.raises(ValueError):
        o.measurement_token((1, 1, 0, 1, 0), [1, 1, 0, 1, "", value, 0., 0.])


@pytest.mark.parametrize("key", [None, (1, 2), (1, 2, 0, 1, -1), (1, 2, True, 1, 0), (1, 2, 0, 1, 2**63)])
def test_invalid_key(key):
    with pytest.raises(ValueError):
        o.measurement_token(key, [1, 1, 0, 1, "", 0., 0., 0.])


def test_randomized_independent_oracle():
    rng = random.Random(20260914)
    for _ in range(300):
        values = [token(rng.randrange(20)) for _ in range(rng.randrange(150))]
        k, w = rng.randrange(1, 12), rng.randrange(1, 30)
        assert list(o.winnow(iter(values), k, w)) == o.reference_winnow(values, k, w)


def test_shifted_32_row_copy_always_has_common_candidate():
    common = [token(i) for i in range(100, 132)]
    for shift in range(40):
        left = [token(i) for i in range(shift)] + common + [token(999)]*7
        right = [token(888)]*17 + common + [token(777)]*11
        a = {h for i,h in o.winnow(left) if shift <= i <= shift+32-o.K}
        b = {h for i,h in o.winnow(right) if 17 <= i <= 17+32-o.K}
        assert a & b


def test_rightmost_ties_short_and_chunk_boundaries():
    values = [token(1)]*40
    assert [i for i,_ in o.winnow(values)] == list(range(24, 33))
    assert list(o.winnow(values[:31])) == []
    from itertools import chain
    assert list(o.winnow(chain(values[:13], values[13:25], values[25:]))) == list(o.winnow(values))


def test_exact_confirmation_not_hash_or_identity():
    a = [token(i) for i in range(32)]
    assert o.confirm_projection(a, iter(a))
    assert not o.confirm_projection(a, a[:-1])
    assert not o.confirm_projection(a[:-1], a[:-1])
    assert not o.confirm_projection(a, a[:-1]+[token(999)])
    with pytest.raises(ValueError):
        o.confirm_projection([b"bad"], [b"bad"])


@pytest.mark.parametrize("k,w", [(0,1),(1,0),(True,2),(2,True),(-1,2)])
def test_invalid_parameters(k, w):
    with pytest.raises(ValueError):
        list(o.winnow([], k, w))
    with pytest.raises(ValueError):
        o.reference_winnow([], k, w)
