# Shared helpers: AC in-game Python is 3.3 — block syntax/features it cannot run.
# Python 3.3 compatible — stdlib only

import ast
import os

AC_APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ac_app"))

# Parsed with the repo's Python; nodes/features AC 3.3 cannot execute.
_FORBIDDEN_NODE_TYPES = tuple(
    t for t in (
        getattr(ast, "JoinedStr", None),       # f-strings (3.6+)
        getattr(ast, "AsyncFunctionDef", None),
        getattr(ast, "AsyncFor", None),
        getattr(ast, "AsyncWith", None),
        getattr(ast, "Await", None),
        getattr(ast, "NamedExpr", None),       # walrus (3.8+)
    ) if t is not None
)


class AcPython33Visitor(ast.NodeVisitor):
    """Collect AC-incompatible syntax in a single source file."""

    def __init__(self, path):
        self.path = path
        self.errors = []

    def generic_visit(self, node):
        if isinstance(node, _FORBIDDEN_NODE_TYPES):
            self.errors.append(
                "%s:%d uses %s (not supported in AC Python 3.3)"
                % (self.path, node.lineno, type(node).__name__)
            )
        super(AcPython33Visitor, self).generic_visit(node)

    def visit_Dict(self, node):
        for key in node.keys:
            if key is None:
                self.errors.append(
                    "%s:%d uses dict ** unpacking (not supported in AC Python 3.3)"
                    % (self.path, getattr(node, "lineno", 0))
                )
        self.generic_visit(node)

    def visit_BinOp(self, node):
        if isinstance(node.op, ast.MatMult):
            self.errors.append(
                "%s:%d uses @ matrix multiply (not supported in AC Python 3.3)"
                % (self.path, node.lineno)
            )
        self.generic_visit(node)


def iter_ac_app_sources():
    for dirpath, dirnames, filenames in os.walk(AC_APP_ROOT):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "data")]
        for name in filenames:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def check_python33_compat(source_path):
    with open(source_path, "r") as fh:
        source = fh.read()
    compile(source, source_path, "exec")
    tree = ast.parse(source, filename=source_path)
    visitor = AcPython33Visitor(source_path)
    visitor.visit(tree)
    return visitor.errors
