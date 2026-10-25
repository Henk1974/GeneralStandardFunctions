"""FUNCTIONS.md moet altijd overeenkomen met de code, en alles wat publiek
is moet een docstring hebben (PEP 257)."""

import importlib
import inspect
import pkgutil
import sys
from pathlib import Path

import general_standard_functions

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from generate_functions_doc import generate  # noqa: E402


def _public_objects():
    for info in pkgutil.walk_packages(general_standard_functions.__path__, "general_standard_functions."):
        module = importlib.import_module(info.name)
        yield info.name, module
        for name in getattr(module, "__all__", ()):
            obj = getattr(module, name)
            if inspect.isclass(obj) or inspect.isfunction(obj):
                yield f"{info.name}.{name}", obj
                if inspect.isclass(obj):
                    for attr, member in vars(obj).items():
                        if not attr.startswith("_") and inspect.isfunction(member):
                            yield f"{info.name}.{name}.{attr}", member


def test_functions_doc_is_up_to_date():
    current = (ROOT / "FUNCTIONS.md").read_text(encoding="utf-8")
    assert current == generate(), "FUNCTIONS.md loopt achter: draai python tools/generate_functions_doc.py"


def test_every_public_object_has_a_docstring():
    missing = [name for name, obj in _public_objects() if not inspect.getdoc(obj)]
    assert not missing, f"Docstring ontbreekt: {missing}"


def test_every_module_declares_all():
    for info in pkgutil.walk_packages(general_standard_functions.__path__, "general_standard_functions."):
        if not info.ispkg:
            assert hasattr(importlib.import_module(info.name), "__all__"), info.name
