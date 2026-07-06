import os
import pytest

from dwim.config import DEFAULT_MODEL
from dwim.engine import suggest

pytestmark = pytest.mark.skipif(
    os.environ.get("DWIM_LIVE") != "1",
    reason="set DWIM_LIVE=1 to run the real-model smoke test (downloads model)",
)


def test_live_corrects_brw():
    out = suggest("brw install pip", 127, DEFAULT_MODEL)
    assert out is not None
    assert "brew" in out
    assert "pip" in out
