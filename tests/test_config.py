from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_config_has_paper_and_molecules():
    cfg = yaml.safe_load((ROOT / "config" / "paper.yaml").read_text(encoding="utf-8"))
    assert cfg["source_paper"]["doi"] == "10.1016/j.jtice.2018.07.011"
    assert len(cfg["molecules"]) == 6
    assert cfg["project"]["mode"] == "open_source_headless"
