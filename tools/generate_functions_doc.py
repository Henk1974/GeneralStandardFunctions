"""Maak FUNCTIONS.md uit de docstrings van het pakket.

De docstrings (PEP 257, Google-stijl) zijn de enige bron; FUNCTIONS.md is
daar een afgeleide van. Draai dit na elke wijziging:

    python tools/generate_functions_doc.py

De test ``tests/test_functions_doc.py`` faalt zolang FUNCTIONS.md niet
overeenkomt met de code.
"""

from __future__ import annotations

import dataclasses
import enum
import importlib
import inspect
import pkgutil
import re
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import general_standard_functions  # noqa: E402

OUTPUT = ROOT / "FUNCTIONS.md"
PACKAGE = general_standard_functions.__name__

# Google-stijl sectienamen in de docstrings, met hun kopje in het document.
_SECTIONS = {
    "Args": "Argumenten",
    "Returns": "Geeft terug",
    "Yields": "Levert",
    "Raises": "Fouten",
    "Attributes": "Velden",
    "Values": "Waarden",
    "Example": "Voorbeeld",
}
_PLAIN_SECTIONS = {"Returns", "Yields"}
_SECTION_RE = re.compile(r"^(\w+):$")
_RST_LITERAL_RE = re.compile(r"``([^`]+)``")

_HEADER = f"""# GeneralStandardFunctions: functieoverzicht

> Gegenereerd uit de docstrings met `python tools/generate_functions_doc.py`.
> Niet met de hand bewerken: pas de docstring aan en genereer opnieuw.

Herbruikbare Python-functies voor (web)projecten. Dit document beschrijft
elke publieke functie en klasse, zodat je de code niet hoeft te lezen.

## Installeren

In `requirements.txt` van een project (vaste versie, zodat een update van
dit pakket nooit ongemerkt een app verandert):

```text
general-standard-functions[web,postgres,storage] @ git+https://github.com/Henk1974/GeneralStandardFunctions.git@v{general_standard_functions.__version__}
```

| Extra | Nodig voor | Installeert |
|---|---|---|
| *(geen)* | `validation`, `localtime`, `security`, `mail` | itsdangerous, tzdata |
| `web` | `web.csrf`, `web.errors` | Flask |
| `postgres` | `db.migrations` (standaard-driver) | psycopg2-binary |
| `storage` | `storage.supabase` | requests |

Tijdens het ontwikkelen aan dit pakket naast een app:
`pip install -e "../GeneralStandardFunctions[all]"`.

## Afspraken

- Importeer uit het submodule: `from {PACKAGE}.validation.email import normalize_email`.
- Instellingen die per app verschillen (domeinen, wachtwoordeisen, tijdzone,
  teksten) zijn argumenten met een redelijke standaard; leg de keuzes van een
  app vast op één plek in die app.
- Foutmeldingen in uitzonderingen zijn Nederlands en bedoeld om aan de
  gebruiker te tonen, tenzij anders vermeld.
- Niets in dit pakket leest zelf omgevingsvariabelen of `.env`; dat doet de app.
"""


def _modules() -> list[ModuleType]:
    names = [info.name for info in pkgutil.walk_packages(general_standard_functions.__path__, f"{PACKAGE}.")]
    return [importlib.import_module(name) for name in sorted(names)]


def _short(module_name: str) -> str:
    return module_name.removeprefix(f"{PACKAGE}.")


def _summary(obj: object) -> str:
    doc = inspect.getdoc(obj) or ""
    return doc.split("\n\n", 1)[0].replace("\n", " ")


def _render_docstring(doc: str | None) -> str:
    """Zet een Google-stijl docstring om naar Markdown.

    Herkent de secties uit ``_SECTIONS`` en RST-codeblokken (een regel die
    op ``::`` eindigt, gevolgd door ingesprongen regels).
    """
    if not doc:
        return "*Geen beschrijving.*\n"
    out: list[str] = []
    section: str | None = None
    code_indent: int | None = None  # inspringing van het open codeblok
    for raw in doc.splitlines():
        if code_indent is not None:
            if not raw.strip() and out[-1] == "```python":
                continue  # geen lege eerste regel in een codeblok
            if not raw.strip() or raw.startswith(" " * code_indent):
                out.append(raw[code_indent:])
                continue
            out = _close_code(out)
            code_indent = None

        match = _SECTION_RE.match(raw)
        if match and match.group(1) in _SECTIONS:
            section = match.group(1)
            out.append(f"\n**{_SECTIONS[section]}:**\n")
            if section == "Example":
                out.append("```python")
                code_indent = 4
            continue

        text = _RST_LITERAL_RE.sub(r"`\1`", raw)
        if section is None:
            if text.rstrip().endswith("::"):
                out += [text.rstrip()[:-1], "", "```python"]
                code_indent = 4
            else:
                out.append(text)
        elif raw.startswith("        "):
            out[-1] += " " + text.strip()
        elif raw.startswith("    "):
            entry = text.strip()
            name, sep, rest = entry.partition(": ")
            if section in _PLAIN_SECTIONS:
                out.append(entry)
            elif sep and " " not in name:
                out.append(f"- `{name.strip('`')}`: {rest}")
            else:
                out.append(f"- {entry}")
        elif not raw.strip():
            section = None
            out.append("")
        else:
            out.append(text)
    if code_indent is not None:
        out = _close_code(out)
    return "\n".join(out).strip() + "\n"


def _close_code(out: list[str]) -> list[str]:
    while out and not out[-1].strip():
        out.pop()
    return [*out, "```", ""]


def _format_annotation(annotation: object) -> str:
    # Met `from __future__ import annotations` zijn annotaties al tekst.
    return annotation if isinstance(annotation, str) else inspect.formatannotation(annotation)


def _format_value(value: object) -> str:
    """Leesbare, vaste weergave (verzamelingen gesorteerd, dataclasses kort)."""
    if isinstance(value, (frozenset, set)):
        return "{" + ", ".join(repr(item) for item in sorted(value)) + "}"
    if dataclasses.is_dataclass(value) and not isinstance(value, type) and value == type(value)():
        return f"{type(value).__name__}()"
    return repr(value)


def _format_default(value: object, module: ModuleType) -> str:
    if inspect.isbuiltin(value) or inspect.isfunction(value) or inspect.isclass(value):
        return value.__name__
    # Een standaardwaarde die een constante van het module is: toon de naam.
    if not isinstance(value, (bool, int, float, type(None))):
        for name in getattr(module, "__all__", ()):
            if getattr(module, name) is value:
                return name
    return _format_value(value)


def _signature(obj: object, module: ModuleType) -> str:
    """Signatuur zoals in de code geschreven, zonder aanhalingstekens rond types."""
    try:
        signature = inspect.signature(obj)
    except (TypeError, ValueError):
        return "(...)"
    params = []
    for param in signature.parameters.values():
        if param.name == "self":
            continue
        text = param.name
        if param.kind is param.VAR_POSITIONAL:
            text = f"*{text}"
        elif param.kind is param.VAR_KEYWORD:
            text = f"**{text}"
        if param.annotation is not param.empty:
            text += f": {_format_annotation(param.annotation)}"
        if param.default is not param.empty:
            separator = " = " if param.annotation is not param.empty else "="
            text += f"{separator}{_format_default(param.default, module)}"
        params.append(text)
    result = f"({', '.join(params)})"
    if not inspect.isclass(obj) and signature.return_annotation is not signature.empty:
        result += f" -> {_format_annotation(signature.return_annotation)}"
    return result


def _render_class(name: str, cls: type, module: ModuleType) -> list[str]:
    if issubclass(cls, BaseException):
        bases = ", ".join(base.__name__ for base in cls.__bases__)
        lines = [f"#### `{name}` (uitzondering, subklasse van `{bases}`)\n"]
    elif issubclass(cls, enum.Enum):
        values = ", ".join(f"`{member.name}`" for member in cls)
        lines = [f"#### `{name}` (enum: {values})\n"]
    elif getattr(cls, "_is_protocol", False):
        lines = [f"#### `{name}` (protocol)\n"]
    else:
        lines = [f"#### `{name}{_signature(cls, module)}`\n"]
    lines.append(_render_docstring(inspect.getdoc(cls)))
    if issubclass(cls, (BaseException, enum.Enum)):
        return lines
    for attr, member in cls.__dict__.items():
        if attr.startswith("_"):
            continue
        func = member.__func__ if isinstance(member, (staticmethod, classmethod)) else member
        if inspect.isfunction(func):
            lines.append(f"##### `{name}.{attr}{_signature(func, module)}`\n")
            lines.append(_render_docstring(inspect.getdoc(func)))
    return lines


def _render_constant(name: str, value: object) -> list[str]:
    shown = _format_value(value)
    if len(shown) > 160:
        shown = shown[:157] + "..."
    return [f"#### `{name}`\n", f"Constante, waarde: `{shown}`\n"]


def _render_module(module: ModuleType) -> list[str]:
    lines = [f"### `{_short(module.__name__)}`\n", _render_docstring(inspect.getdoc(module))]
    for name in module.__all__:
        obj = getattr(module, name)
        if inspect.isclass(obj):
            lines += _render_class(name, obj, module)
        elif inspect.isfunction(obj):
            lines += [f"#### `{name}{_signature(obj, module)}`\n", _render_docstring(inspect.getdoc(obj))]
        else:
            lines += _render_constant(name, obj)
    return lines


def generate() -> str:
    """Geef de volledige inhoud van FUNCTIONS.md."""
    modules = [m for m in _modules() if hasattr(m, "__all__")]
    packages = [m for m in _modules() if not hasattr(m, "__all__")]

    toc = ["## Inhoud\n", "| Module | Waarvoor |", "|---|---|"]
    toc += [f"| [`{_short(m.__name__)}`](#{_short(m.__name__).replace('.', '')}) | {_summary(m)} |" for m in modules]

    body: list[str] = []
    for package in packages:
        prefix = f"{package.__name__}."
        members = [m for m in modules if m.__name__.startswith(prefix) and m.__name__.count(".") == package.__name__.count(".") + 1]
        if not members:
            continue
        body += [f"## `{_short(package.__name__)}`\n", _render_docstring(inspect.getdoc(package))]
        for module in members:
            body += _render_module(module)
    top_level = [m for m in modules if m.__name__.count(".") == 1]
    if top_level:
        body += ["## Losse modules\n"]
        for module in top_level:
            body += _render_module(module)

    text = "\n".join([_HEADER, *toc, "", *body])
    return re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"


def main() -> None:
    OUTPUT.write_text(generate(), encoding="utf-8", newline="\n")
    print(f"Geschreven: {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
