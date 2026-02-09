from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp_tests"


@pytest.fixture
def local_tmp_dir() -> Path:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    target = TEST_TMP_ROOT / f"case_{uuid.uuid4().hex}"
    target.mkdir(parents=True, exist_ok=True)
    yield target
    shutil.rmtree(target, ignore_errors=True)
