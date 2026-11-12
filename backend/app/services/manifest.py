import re
import configparser
from typing import Dict, Any, List, Optional

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # Fallback to manual parsing


def parse_requirements_txt(content: str) -> Dict[str, Any]:
    """Safely extracts package names and version pins from requirements.txt."""
    packages: List[str] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip inline comments
        if "#" in line:
            line = line.split("#")[0].strip()
        if line:
            packages.append(line)
    return {"packages": packages, "count": len(packages)}


def parse_pyproject_toml(content: str) -> Dict[str, Any]:
    """Safely parses pyproject.toml without external dependencies."""
    result: Dict[str, Any] = {
        "build_backend": None,
        "dependencies": [],
        "dev_dependencies": [],
        "has_pytest_config": False,
    }

    if tomllib is not None:
        try:
            data = tomllib.loads(content)
            # Build backend
            build_system = data.get("build-system", {})
            result["build_backend"] = build_system.get("build-backend")

            # Standard PEP 621 dependencies
            project = data.get("project", {})
            deps = project.get("dependencies", [])
            if isinstance(deps, list):
                result["dependencies"].extend(deps)

            opt_deps = project.get("optional-dependencies", {})
            if isinstance(opt_deps, dict):
                for group, group_deps in opt_deps.items():
                    if isinstance(group_deps, list):
                        result["dev_dependencies"].extend(group_deps)

            # Poetry dependencies
            tool = data.get("tool", {})
            poetry = tool.get("poetry", {})
            if poetry:
                poetry_deps = poetry.get("dependencies", {})
                if isinstance(poetry_deps, dict):
                    result["dependencies"].extend(list(poetry_deps.keys()))
                group_dev = poetry.get("group", {}).get("dev", {}).get("dependencies", {})
                if isinstance(group_dev, dict):
                    result["dev_dependencies"].extend(list(group_dev.keys()))

            # Check for pytest config
            if "pytest" in tool or "pytest" in data:
                result["has_pytest_config"] = True

            return result
        except Exception:
            pass

    # Simple regex fallback if tomllib parsing fails or is unavailable
    if "[tool.pytest" in content or "pytest" in content:
        result["has_pytest_config"] = True
    return result


def parse_ini_manifest(content: str) -> Dict[str, Any]:
    """Safely parses ini-style manifests such as setup.cfg, tox.ini, or pytest.ini."""
    cp = configparser.ConfigParser(interpolation=None)
    result: Dict[str, Any] = {"sections": [], "has_pytest": False, "has_tox": False}
    try:
        cp.read_string(content)
        result["sections"] = cp.sections()
        for sec in cp.sections():
            if "pytest" in sec:
                result["has_pytest"] = True
            if "tox" in sec:
                result["has_tox"] = True
    except Exception:
        pass
    return result


def detect_manifest_metadata(filename: str, content: str) -> Optional[Dict[str, Any]]:
    """Inspects manifest file and returns parsed manifest details."""
    lower_name = filename.lower()
    if lower_name.startswith("requirements") and lower_name.endswith(".txt"):
        return {"manifest_type": "requirements.txt", "data": parse_requirements_txt(content)}
    elif lower_name == "pyproject.toml":
        return {"manifest_type": "pyproject.toml", "data": parse_pyproject_toml(content)}
    elif lower_name in ("setup.cfg", "tox.ini", "pytest.ini"):
        return {"manifest_type": lower_name, "data": parse_ini_manifest(content)}
    elif lower_name in ("pipfile", "pipfile.lock"):
        return {"manifest_type": lower_name, "data": {"type": lower_name}}
    return None
