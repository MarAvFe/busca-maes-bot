import re
from pathlib import Path


def test_version_is_semver():
    version = Path(__file__).parent.parent.joinpath("VERSION").read_text().strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), (
        f"VERSION file contains invalid semver: {version!r}"
    )
