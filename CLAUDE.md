# Instructies voor dit project

- Lees eerst `FUNCTIONS.md`: daarin staat elke publieke functie en klasse.
  Lees de broncode alleen als je iets wijzigt.
- Werk volgens de PEP's, vooral PEP 20 (eenvoudig, expliciet, leesbaar),
  PEP 8 en PEP 257. Docstrings in het Nederlands, Google-stijl
  (`Args`/`Returns`/`Raises`/`Example`); namen in het Engels.
- Na elke wijziging: `python tools/generate_functions_doc.py` en
  `python -m pytest` (draait ook de docstring-voorbeelden en controleert dat
  FUNCTIONS.md bij is).
- Elk module heeft een `__all__`; alleen wat daarin staat is publiek en komt
  in FUNCTIONS.md.
- Geen app-specifieke code en niets dat zelf `os.environ` of `.env` leest:
  instellingen komen als argument binnen.
- Nieuwe afhankelijkheden alleen als optionele extra in `pyproject.toml`,
  tenzij elk onderdeel ze nodig heeft.
