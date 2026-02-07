from pathlib import Path

from local_review_copilot.config import WorkspaceConfig
from local_review_copilot.scanner import scan_workspace


def test_scan_workspace_filters_supported_files(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# hello", encoding="utf-8")
    (tmp_path / "b.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "c.bin").write_bytes(b"\x00\x01")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "d.md").write_text("skip", encoding="utf-8")

    config = WorkspaceConfig(root_dir=str(tmp_path), ignore_patterns=["node_modules/*"])
    docs = scan_workspace(config)
    paths = {Path(doc.path).name for doc in docs}
    assert "a.md" in paths
    assert "b.txt" in paths
    assert "c.bin" not in paths
    assert "d.md" not in paths

