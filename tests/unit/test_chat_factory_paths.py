"""chat_factory path helpers must not crash in Docker layout."""

from pathlib import Path

from agents.llm import chat_factory


def test_repo_root_does_not_raise_with_shallow_paths(monkeypatch, tmp_path):
    shallow = tmp_path / "agents" / "agents" / "llm"
    shallow.mkdir(parents=True)
    fake = shallow / "chat_factory.py"
    fake.write_text("# stub", encoding="utf-8")

    monkeypatch.setattr(chat_factory, "__file__", str(fake))
    root = chat_factory._repo_root()
    assert isinstance(root, Path)


def test_project_env_file_candidates_does_not_raise_in_shallow_layout(monkeypatch, tmp_path):
    shallow = tmp_path / "agents" / "agents" / "llm"
    shallow.mkdir(parents=True)
    fake = shallow / "chat_factory.py"
    fake.write_text("# stub", encoding="utf-8")

    monkeypatch.setattr(chat_factory, "__file__", str(fake))
    candidates = chat_factory.project_env_file_candidates()
    assert isinstance(candidates, list)
