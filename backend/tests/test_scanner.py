from pathlib import Path

from local_review_copilot.config import WorkspaceConfig
from local_review_copilot.scanner import scan_workspace


def test_scan_workspace_filters_supported_files(local_tmp_dir: Path) -> None:
    (local_tmp_dir / "a.md").write_text("# hello", encoding="utf-8")
    (local_tmp_dir / "b.txt").write_text("hello", encoding="utf-8")
    (local_tmp_dir / "c.gif").write_bytes(b"GIF89a")
    (local_tmp_dir / "c.bin").write_bytes(b"\x00\x01")
    (local_tmp_dir / "node_modules").mkdir()
    (local_tmp_dir / "node_modules" / "d.md").write_text("skip", encoding="utf-8")

    config = WorkspaceConfig(root_dir=str(local_tmp_dir), ignore_patterns=["node_modules/*"])
    docs = scan_workspace(config)
    paths = {Path(doc.path).name for doc in docs}
    assert "a.md" in paths
    assert "b.txt" in paths
    assert "c.gif" in paths
    assert "c.bin" not in paths
    assert "d.md" not in paths

