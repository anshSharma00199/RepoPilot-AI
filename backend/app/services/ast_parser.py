import ast
from typing import Dict, Any, List, Optional


class PythonAstAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.imports: List[str] = []
        self.classes: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []
        self.test_indicators: List[str] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(alias.name)
            if alias.name in ("pytest", "unittest", "nose", "mock"):
                self.test_indicators.append(f"import:{alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        for alias in node.names:
            full_name = f"{mod}.{alias.name}" if mod else alias.name
            self.imports.append(full_name)
            if "pytest" in mod or "unittest" in mod:
                self.test_indicators.append(f"import:{full_name}")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        bases = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
            elif isinstance(b, ast.Attribute):
                bases.append(f"{ast.unparse(b) if hasattr(ast, 'unparse') else b.attr}")

        is_test_class = node.name.startswith("Test") or any("TestCase" in base for base in bases)
        if is_test_class:
            self.test_indicators.append(f"class:{node.name}")

        self.classes.append({
            "name": node.name,
            "lineno": node.lineno,
            "bases": bases,
            "is_test_class": is_test_class,
        })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._record_func(node, is_async=False)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._record_func(node, is_async=True)
        self.generic_visit(node)

    def _record_func(self, node, is_async: bool):
        is_test_func = node.name.startswith("test_") or node.name.endswith("_test")
        if is_test_func:
            self.test_indicators.append(f"func:{node.name}")

        decorators = []
        for d in node.decorator_list:
            if isinstance(d, ast.Name):
                decorators.append(d.id)
            elif isinstance(d, ast.Attribute):
                decorators.append(d.attr)
            elif hasattr(ast, "unparse"):
                decorators.append(ast.unparse(d))

        self.functions.append({
            "name": node.name,
            "lineno": node.lineno,
            "is_async": is_async,
            "decorators": decorators,
            "is_test_func": is_test_func,
        })


def analyze_python_source(source_code: str, filename: str = "<unknown>") -> Dict[str, Any]:
    """
    Parses Python code into an AST and extracts structural metadata.
    Never executes or imports the target code.
    Catches SyntaxError and ValueError gracefully and returns them as analysis findings.
    """
    result: Dict[str, Any] = {
        "success": False,
        "imports": [],
        "classes": [],
        "functions": [],
        "test_indicators": [],
        "has_test_elements": False,
        "syntax_error": None,
    }

    try:
        tree = ast.parse(source_code, filename=filename)
        analyzer = PythonAstAnalyzer()
        analyzer.visit(tree)

        result["success"] = True
        result["imports"] = analyzer.imports
        result["classes"] = analyzer.classes
        result["functions"] = analyzer.functions
        result["test_indicators"] = analyzer.test_indicators
        result["has_test_elements"] = len(analyzer.test_indicators) > 0

    except SyntaxError as e:
        result["syntax_error"] = {
            "message": str(e.msg),
            "lineno": e.lineno,
            "offset": e.offset,
            "text": e.text.strip() if e.text else None,
        }
    except Exception as e:
        result["syntax_error"] = {
            "message": f"Parse exception: {str(e)}",
            "lineno": None,
            "offset": None,
            "text": None,
        }

    return result
