# GeneralStandardFunctions

Herbruikbare Python-functies voor Henks (web)projecten: invoercontrole,
tijdzones, beveiliging (CSRF, inlogblokkade, tokens, captcha,
secrets-controle), databaseverbindingen en migraties, mail en
bestandsopslag.

**Alle functies staan beschreven in [FUNCTIONS.md](FUNCTIONS.md)**, zodat je
de code niet hoeft te lezen.

## Gebruiken in een project

Zet in `requirements.txt` (altijd een vaste versie):

```text
general-standard-functions[web,postgres,storage] @ git+https://github.com/Henk1974/GeneralStandardFunctions.git@v0.2.0
```

Kies alleen de extra's die je nodig hebt; zie de tabel in FUNCTIONS.md.

## Ontwikkelen

```bash
py -3.11 -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe -m pytest
```

Werkwijze bij een wijziging:

1. Pas code en docstring aan (PEP 8, PEP 257, PEP 20). De docstring is de
   enige beschrijving: Google-stijl met `Args`, `Returns`, `Raises` en waar
   nuttig een `Example`. De voorbeelden worden als test uitgevoerd.
2. Schrijf of pas tests aan in `tests/`.
3. Maak het overzicht opnieuw: `python tools/generate_functions_doc.py`.
   De tests falen zolang FUNCTIONS.md achterloopt.
4. Verhoog de versie in `pyproject.toml` en `src/general_standard_functions/__init__.py`
   ([semantic versioning](https://semver.org/lang/nl/): een wijziging die
   bestaande apps kan breken is een nieuwe hoofdversie), commit en maak een
   tag, bijvoorbeeld `git tag v0.2.0 && git push --tags`.
5. Werk in een app de versie in `requirements.txt` bij als je de nieuwe
   versie daar wilt gebruiken.

## Wat hoort hier wel en niet

Wel: code die in elke (web)app hetzelfde werkt, met instellingen als
argument. Niet: alles wat over één specifieke app gaat (bier, kelders,
gebruikersrollen) en alles wat zelf omgevingsvariabelen leest.

## Licentie

GPL-3.0-or-later, zie [LICENSE](LICENSE).
