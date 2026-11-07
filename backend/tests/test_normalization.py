import pytest

from src.utils.normalization import normalize_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ONE STEELS", "one_steels"),
        (" ", ""),
        ("Ltd/Limited", ""),
        ("A-One Steels Ltd", "a_one_steels"),
        ("A One Steels Limited", "a_one_steels"),
        ("  A-One   Steels  ", "a_one_steels"),
        ("Muthoot & Sons", "muthoot_sons"),
        (None, ""),
        ("", ""),
        ("Ltdco Industries", "ltdco_industries"),
    ],
)
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected