"""Shared fixtures: the Ancud sample PDF (codigo ba26352019)."""
from pathlib import Path

import pytest

ANCUD_PDF = Path(__file__).resolve().parents[1] / "phase0" / "sample_pdfs" / "EX_2profile_10_6_1.pdf"


@pytest.fixture(scope="session")
def ancud_pdf():
    if not ANCUD_PDF.exists():
        pytest.skip(f"sample PDF not present: {ANCUD_PDF}")
    return str(ANCUD_PDF)
