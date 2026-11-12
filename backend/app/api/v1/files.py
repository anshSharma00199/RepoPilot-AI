from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.schemas.repository_file import (
    RepositoryFileResponse,
    RepositoryFileListResponse,
    FileTreeNode,
)

router = APIRouter(prefix="/repositories/{repo_id}", tags=["Files"])


@router.get("/files", response_model=RepositoryFileListResponse)
def list_repository_files(
    repo_id: str,
    classification: Optional[str] = Query(None, description="Filter by classification: source_code, test, configuration, documentation, generated_output, binary_data, other"),
    file_status: Optional[str] = Query(None, alias="status", description="Filter by status: inventoried, content_analyzed, skipped, failed"),
    language: Optional[str] = Query(None, description="Filter by language e.g. python, markdown"),
    is_test: Optional[bool] = Query(None, description="Filter test files"),
    is_manifest: Optional[bool] = Query(None, description="Filter manifest files"),
    has_syntax_error: Optional[bool] = Query(None, description="Filter files with syntax errors"),
    search: Optional[str] = Query(None, description="Search relative path"),
    entry_type: Optional[str] = Query("file", description="Filter by entry_type: file, directory, or null for all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Lists repository files with comprehensive filtering, search, and pagination."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "REPOSITORY_NOT_FOUND", "message": "Repository not found."},
        )

    query = db.query(RepositoryFile).filter(RepositoryFile.repository_id == repo_id)

    if entry_type:
        query = query.filter(RepositoryFile.entry_type == entry_type)
    if classification:
        query = query.filter(RepositoryFile.classification == classification)
    if file_status:
        query = query.filter(RepositoryFile.status == file_status)
    if language:
        query = query.filter(RepositoryFile.language == language)
    if is_test is not None:
        query = query.filter(RepositoryFile.is_test == is_test)
    if is_manifest is not None:
        query = query.filter(RepositoryFile.is_manifest == is_manifest)
    if search:
        query = query.filter(RepositoryFile.relative_path.ilike(f"%{search}%"))

    all_items = query.order_by(RepositoryFile.relative_path).all()

    # In-memory filter for JSON syntax error flag if requested
    if has_syntax_error is not None:
        filtered = []
        for f in all_items:
            has_err = bool(f.ast_metadata and f.ast_metadata.get("syntax_error"))
            if has_err == has_syntax_error:
                filtered.append(f)
        all_items = filtered

    total = len(all_items)
    start = (page - 1) * page_size
    paged_items = all_items[start : start + page_size]

    return RepositoryFileListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[RepositoryFileResponse.model_validate(f) for f in paged_items],
    )


@router.get("/tree", response_model=FileTreeNode)
def get_repository_tree(repo_id: str, db: Session = Depends(get_db)):
    """
    Constructs and returns a hierarchical tree structure of directories and files
    for the repository explorer.
    """
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "REPOSITORY_NOT_FOUND", "message": "Repository not found."},
        )

    files = db.query(RepositoryFile).filter(RepositoryFile.repository_id == repo_id).all()

    root_node = FileTreeNode(
        name=repo.name,
        relative_path="",
        entry_type="directory",
        children=[],
    )

    # Lookup mapping for directory nodes: relative_path -> node
    dir_lookup: Dict[str, FileTreeNode] = {"": root_node}

    # First pass: sort by path depth and name
    sorted_files = sorted(files, key=lambda f: (f.relative_path.count("/"), f.entry_type == "file", f.relative_path))

    for f in sorted_files:
        parts = f.relative_path.split("/")
        name = parts[-1]
        parent_path = "/".join(parts[:-1])

        # Ensure all intermediate parent directory nodes exist in tree
        curr_parent = root_node
        accum_path = ""
        for p in parts[:-1]:
            accum_path = f"{accum_path}/{p}" if accum_path else p
            if accum_path not in dir_lookup:
                new_dir_node = FileTreeNode(
                    name=p,
                    relative_path=accum_path,
                    entry_type="directory",
                    children=[],
                )
                dir_lookup[accum_path] = new_dir_node
                curr_parent.children.append(new_dir_node)
            curr_parent = dir_lookup[accum_path]

        has_syntax_err = bool(f.ast_metadata and f.ast_metadata.get("syntax_error"))

        if f.entry_type == "directory":
            if f.relative_path not in dir_lookup:
                d_node = FileTreeNode(
                    name=name,
                    relative_path=f.relative_path,
                    entry_type="directory",
                    file_id=f.id,
                    status=f.status,
                    skip_reason=f.skip_reason,
                    is_test=f.is_test,
                    children=[],
                )
                dir_lookup[f.relative_path] = d_node
                curr_parent.children.append(d_node)
            else:
                # Update existing directory node with DB metadata
                existing = dir_lookup[f.relative_path]
                existing.file_id = f.id
                existing.status = f.status
                existing.skip_reason = f.skip_reason
                existing.is_test = f.is_test
        else:
            file_node = FileTreeNode(
                name=name,
                relative_path=f.relative_path,
                entry_type="file",
                file_id=f.id,
                language=f.language,
                classification=f.classification,
                status=f.status,
                skip_reason=f.skip_reason,
                file_size_bytes=f.file_size_bytes,
                is_test=f.is_test,
                is_manifest=f.is_manifest,
                has_syntax_error=has_syntax_err,
                children=[],
            )
            curr_parent.children.append(file_node)

    # Sort children: directories first, then alphabetically
    def sort_tree_children(node: FileTreeNode):
        node.children.sort(key=lambda c: (0 if c.entry_type == "directory" else 1, c.name.lower()))
        for c in node.children:
            if c.entry_type == "directory":
                sort_tree_children(c)

    sort_tree_children(root_node)
    return root_node


@router.get("/files/{file_id}", response_model=RepositoryFileResponse)
def get_file_details(repo_id: str, file_id: str, db: Session = Depends(get_db)):
    """Gets complete metadata and AST findings for a single repository file."""
    file_record = (
        db.query(RepositoryFile)
        .filter(RepositoryFile.repository_id == repo_id, RepositoryFile.id == file_id)
        .first()
    )
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "FILE_NOT_FOUND", "message": "File not found in repository."},
        )
    return RepositoryFileResponse.model_validate(file_record)
