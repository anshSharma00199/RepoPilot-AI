from tests.fixtures.archive_factory import create_sample_repo_zip


def test_api_full_workflow(client):
    """
    End-to-end API integration test:
    1. Upload valid sample repository ZIP.
    2. Verify status and metrics rollup.
    3. Query repository tree hierarchy.
    4. Query files list with filtering.
    5. Query single file details with AST metadata.
    6. Delete repository.
    """
    # 1. Upload valid sample ZIP
    zip_bytes = create_sample_repo_zip()
    files = {"file": ("sample_repo.zip", zip_bytes, "application/zip")}
    upload_res = client.post("/api/v1/repositories/upload", files=files)
    assert upload_res.status_code == 201
    repo_data = upload_res.json()
    repo_id = repo_data["id"]
    assert repo_data["name"] == "sample_repo"
    assert repo_data["status"] == "completed"

    scan = repo_data["latest_scan"]
    assert scan is not None
    assert scan["status"] == "completed"
    assert scan["total_files"] >= 5
    assert scan["supported_source_files"] >= 1
    assert scan["test_files"] >= 1
    assert scan["manifest_files"] >= 1
    assert scan["parse_errors"] >= 1
    assert "pytest" in scan["detected_frameworks"]

    # 2. List repositories
    list_res = client.get("/api/v1/repositories")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    matching = [r for r in list_data["items"] if r["id"] == repo_id]
    assert len(matching) == 1

    # 3. Get repository details
    detail_res = client.get(f"/api/v1/repositories/{repo_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == repo_id
    assert len(detail_data["recent_scans"]) >= 1

    # 4. Get directory tree
    tree_res = client.get(f"/api/v1/repositories/{repo_id}/tree")
    assert tree_res.status_code == 200
    tree_data = tree_res.json()
    assert tree_data["entry_type"] == "directory"
    child_names = [c["name"] for c in tree_data["children"]]
    assert "src" in child_names or "tests" in child_names or "requirements.txt" in child_names

    # 5. List files with filters
    # 5a. Filter test files
    tests_res = client.get(f"/api/v1/repositories/{repo_id}/files?classification=test")
    assert tests_res.status_code == 200
    tests_data = tests_res.json()
    assert tests_data["total"] >= 1
    for f in tests_data["items"]:
        assert f["classification"] == "test"

    # 5b. Filter manifests
    manifests_res = client.get(f"/api/v1/repositories/{repo_id}/files?is_manifest=true")
    assert manifests_res.status_code == 200
    manifests_data = manifests_res.json()
    assert manifests_data["total"] >= 1
    for f in manifests_data["items"]:
        assert f["is_manifest"] is True

    # 5c. Filter syntax errors
    syntax_res = client.get(f"/api/v1/repositories/{repo_id}/files?has_syntax_error=true")
    assert syntax_res.status_code == 200
    syntax_data = syntax_res.json()
    assert syntax_data["total"] >= 1
    broken_file = syntax_data["items"][0]
    assert "broken_syntax.py" in broken_file["relative_path"]

    # 5d. Search files
    search_res = client.get(f"/api/v1/repositories/{repo_id}/files?search=calculator")
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total"] >= 1
    assert any("calculator" in f["relative_path"] for f in search_data["items"])

    # 6. Single file detail inspection
    calc_file = next(f for f in search_data["items"] if f["relative_path"] == "src/calculator.py")
    file_detail_res = client.get(f"/api/v1/repositories/{repo_id}/files/{calc_file['id']}")
    assert file_detail_res.status_code == 200
    file_detail = file_detail_res.json()
    assert file_detail["ast_metadata"] is not None
    classes = [c["name"] for c in file_detail["ast_metadata"]["classes"]]
    assert "Calculator" in classes

    # 7. Delete repository
    del_res = client.delete(f"/api/v1/repositories/{repo_id}")
    assert del_res.status_code == 204

    # Verify repository is gone
    not_found_res = client.get(f"/api/v1/repositories/{repo_id}")
    assert not_found_res.status_code == 404
