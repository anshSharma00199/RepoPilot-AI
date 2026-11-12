from pathlib import Path

from app.services.retriever import _resolve_repository_file


def test_resolves_traceback_path_inside_single_wrapper_directory(tmp_path: Path):
    repo_root = tmp_path / "extracted"
    source = repo_root / "repopilot_demo_project" / "src" / "shop.py"
    source.parent.mkdir(parents=True)
    source.write_text("def average_rating(ratings):\n    return sum(ratings) / len(ratings)\n", encoding="utf-8")

    resolved = _resolve_repository_file(repo_root, "src/shop.py")

    assert resolved == source.resolve()
    assert "len(ratings)" in resolved.read_text(encoding="utf-8")


def test_resolves_docker_workspace_traceback_path(tmp_path: Path):
    repo_root = tmp_path / "extracted"
    source = repo_root / "project" / "src" / "shop.py"
    source.parent.mkdir(parents=True)
    source.write_text("# real source", encoding="utf-8")

    assert _resolve_repository_file(repo_root, "/workspace/src/shop.py") == source.resolve()


def test_does_not_guess_when_suffix_matches_multiple_files(tmp_path: Path):
    repo_root = tmp_path / "extracted"
    for folder in ("one", "two"):
        source = repo_root / folder / "src" / "shop.py"
        source.parent.mkdir(parents=True)
        source.write_text(folder, encoding="utf-8")

    assert _resolve_repository_file(repo_root, "src/shop.py") is None


def test_retriever_includes_source_from_disk_when_index_is_empty(tmp_path: Path):
    from types import SimpleNamespace

    from app.services.retriever import retrieve_diagnostic_context

    source = tmp_path / "wrapper" / "src" / "shop.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def average_rating(ratings):\n    return sum(ratings) / len(ratings)\n",
        encoding="utf-8",
    )

    class EmptyQuery:
        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return []

    class EmptyDB:
        def query(self, *args, **kwargs):
            return EmptyQuery()

    repository = SimpleNamespace(id="repo-1", storage_path=str(tmp_path))
    job = SimpleNamespace(
        failures=[], stdout="", stderr="", exit_code=1,
        command=["pytest"], error_type="test_failure", error_message="tests failed",
    )

    context = retrieve_diagnostic_context(EmptyDB(), repository, job)

    assert any("shop.py" in snippet.file_path for snippet in context.snippets)
    assert "len(ratings)" in context.formatted_prompt
    assert "No repository files could be read" not in context.formatted_prompt
