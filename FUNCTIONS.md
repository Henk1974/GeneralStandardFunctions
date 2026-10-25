# GeneralStandardFunctions: functieoverzicht

> Gegenereerd uit de docstrings met `python tools/generate_functions_doc.py`.
> Niet met de hand bewerken: pas de docstring aan en genereer opnieuw.

Herbruikbare Python-functies voor (web)projecten. Dit document beschrijft
elke publieke functie en klasse, zodat je de code niet hoeft te lezen.

## Installeren

In `requirements.txt` van een project (vaste versie, zodat een update van
dit pakket nooit ongemerkt een app verandert):

```text
general-standard-functions[web,postgres,storage] @ git+https://github.com/Henk1974/GeneralStandardFunctions.git@v0.2.0
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

- Importeer uit het submodule: `from general_standard_functions.validation.email import normalize_email`.
- Instellingen die per app verschillen (domeinen, wachtwoordeisen, tijdzone,
  teksten) zijn argumenten met een redelijke standaard; leg de keuzes van een
  app vast op één plek in die app.
- Foutmeldingen in uitzonderingen zijn Nederlands en bedoeld om aan de
  gebruiker te tonen, tenzij anders vermeld.
- Niets in dit pakket leest zelf omgevingsvariabelen of `.env`; dat doet de app.

## Inhoud

| Module | Waarvoor |
|---|---|
| [`db.migrations`](#dbmigrations) | Migratie-runner: voer genummerde ``.sql``-bestanden één keer uit, op volgorde. |
| [`db.request_scope`](#dbrequest_scope) | Eén databaseverbinding per webverzoek, met een transactie per blok. |
| [`i18n`](#i18n) | Vertaalhaak voor de meldingen van dit pakket (en van een app zelf). |
| [`localtime`](#localtime) | Tijdstippen opslaan in UTC en tonen in lokale (standaard Nederlandse) tijd. |
| [`mail.smtp`](#mailsmtp) | E-mail versturen via SMTP, alleen met de standaardbibliotheek. |
| [`security.captcha`](#securitycaptcha) | Eenvoudige robotcontrole voor openbare formulieren, zonder externe dienst. |
| [`security.lockout`](#securitylockout) | Inlogpogingen beperken: wanneer blokkeren, wanneer verplicht resetten. |
| [`security.redirects`](#securityredirects) | Veilig doorsturen: nooit naar een andere website (open redirect). |
| [`security.secret_key`](#securitysecret_key) | Controle op de geheime sessiesleutel van een webapp. |
| [`security.secrets_check`](#securitysecrets_check) | Controle: staan er per ongeluk geheimen in bestanden die git bijhoudt? |
| [`security.tokens`](#securitytokens) | Geheime tokens voor links in mails (uitnodigen, wachtwoord herstellen). |
| [`storage.images`](#storageimages) | Geüploade afbeeldingen opslaan onder een willekeurige, unieke naam. |
| [`storage.supabase`](#storagesupabase) | Bestanden uploaden naar Supabase Storage via de REST-API (zonder SDK). |
| [`validation.barcode`](#validationbarcode) | Barcodes (EAN-8, EAN-13, UPC) normaliseren. |
| [`validation.email`](#validationemail) | E-mailadressen controleren en normaliseren. |
| [`validation.password`](#validationpassword) | Wachtwoordbeleid: lengte, verplichte tekensoorten en een zwakke-lijst. |
| [`web.csrf`](#webcsrf) | CSRF-bescherming voor alle formulieren van een Flask-app, zonder extra pakket. |
| [`web.errors`](#weberrors) | Een veilige foutpagina: de gebruiker ziet nooit SQL of een stacktrace. |

## `db`

Database: één verbinding per webverzoek en een eenvoudige migratie-runner.

### `db.migrations`

Migratie-runner: voer genummerde `.sql`-bestanden één keer uit, op volgorde.

Elke wijziging aan de database is een nieuw bestand in de map met
migraties, bijvoorbeeld `021_add_login_lockout.sql`. De runner houdt in de
tabel `schema_migrations` bij wat al is uitgevoerd, dus meerdere keren
draaien is veilig. Elk bestand is één transactie: mislukt het, dan blijft
de database zoals hij was en stopt de runner.

Vereist de extra `postgres` (psycopg2), tenzij je zelf `connect` meegeeft.

#### `pending_migrations(migration_files: list[Path], applied: set[str]) -> list[Path]`

Bepaal welke migraties nog moeten, op volgorde van bestandsnaam.

**Argumenten:**

- `migration_files`: Alle migratiebestanden.
- `applied`: Bestandsnamen die al in `schema_migrations` staan.

**Geeft terug:**

De nog niet uitgevoerde bestanden, gesorteerd.

**Voorbeeld:**

```python
>>> [p.name for p in pending_migrations([Path("002_b.sql"), Path("001_a.sql")], {"001_a.sql"})]
['002_b.sql']
```

#### `run_migrations(database_url: str, migrations_dir: Path, connect: Optional[Callable[[str], Any]] = None, log: Callable[[str], None] = print) -> list[str]`

Voer alle nog niet uitgevoerde migraties uit.

**Argumenten:**

- `database_url`: PostgreSQL-verbindingsstring.
- `migrations_dir`: Map met de `*.sql`-bestanden.
- `connect`: Functie die een verbinding opent; standaard `psycopg2.connect`. Voor tests of een andere driver.
- `log`: Waar voortgangsmeldingen heen gaan; standaard `print`.

**Geeft terug:**

De namen van de uitgevoerde migraties (leeg als er niets te doen was).

**Fouten:**

- `Exception`: De fout van de database bij een mislukte migratie; die migratie en alle volgende zijn dan niet uitgevoerd.

### `db.request_scope`

Eén databaseverbinding per webverzoek, met een transactie per blok.

Een nieuwe verbinding openen kost (zeker serverless) tientallen
milliseconden. `ScopedConnections` hergebruikt daarom binnen één verzoek
dezelfde verbinding; buiten een verzoek (scripts, CLI) krijgt elk blok een
eigen verbinding. Elk `with connection()`-blok is één transactie: commit bij
succes, rollback bij een fout. Een genest blok krijgt een savepoint, zodat
een fout daarin de buitenste transactie heel laat.

Werkt met elke DB-API-verbinding (psycopg2, psycopg 3, ...): je geeft zelf
de functie die een verbinding opent. Gebruik in een Flask-app:

```python
connections = ScopedConnections(lambda: psycopg2.connect(DATABASE_URL), name="bierkelder")

@app.before_request
def _open():
    g.db_scope = connections.begin_request_scope()

@app.teardown_request
def _close(_exc):
    connections.end_request_scope(g.pop("db_scope"))

with connections.connection() as conn:
    ...
```

#### `ScopedConnections(connect: Callable[[], Any], name: str = 'app')`

Beheert databaseverbindingen per verzoek.

**Argumenten:**

- `connect`: Functie zonder argumenten die een nieuwe verbinding opent.
- `name`: Korte naam (kleine letters, cijfers, `_`) voor de contextvar en de savepoints.

**Fouten:**

- `ValueError`: `name` is geen geldige SQL-naam.

##### `ScopedConnections.begin_request_scope() -> Token`

Start de scope van een verzoek.

De verbinding wordt pas bij het eerste gebruik geopend, dus een
verzoek zonder database kost niets.

**Geeft terug:**

Een token voor `end_request_scope`.

##### `ScopedConnections.end_request_scope(token: Token) -> None`

Sluit de scope: draai open werk terug en sluit de verbinding.

**Argumenten:**

- `token`: Het token van `begin_request_scope`.

##### `ScopedConnections.connection() -> Iterator[Any]`

Geef een verbinding voor één transactie.

**Levert:**

De verbinding. Commit gebeurt automatisch aan het eind van het
blok, rollback bij een uitzondering (die daarna doorgaat).

## `mail`

E-mail versturen.

### `mail.smtp`

E-mail versturen via SMTP, alleen met de standaardbibliotheek.

Gemaakt voor Gmail met een app-wachtwoord (`smtp.gmail.com`, poort 587,
STARTTLS), maar werkt met elke SMTP-server. Laat je eigen code afhangen van
het protocol `Mailer`, niet van `SmtpMailer` zelf; dan kun je in tests
een nep-mailer meegeven en lokaal zonder mail werken (`mailer=None`).

#### `Mailer` (protocol)

Alles met deze `send`-methode kan mail versturen.

##### `Mailer.send(to: str, subject: str, body: str, reply_to: Optional[str] = None, from_name: Optional[str] = None) -> None`

Verstuur één tekstmail; zie `SmtpMailer.send`.

#### `MailError` (uitzondering, subklasse van `Exception`)

Versturen is mislukt: verbinding, inloggen of geweigerd door de server.

#### `header_safe(value: str) -> str`

Maak tekst veilig voor een mailheader (geen regeleinden).

Zonder dit kan iemand via een formulierveld extra headers toevoegen,
zoals `Bcc:` (header-injectie).

**Argumenten:**

- `value`: Bijvoorbeeld een onderwerp of naam uit een formulier.

**Geeft terug:**

De tekst op één regel, met enkele spaties.

**Voorbeeld:**

```python
>>> header_safe("Hoi\r\nBcc: spam@example.com")
'Hoi Bcc: spam@example.com'
```

#### `SmtpMailer(host: str, port: int, username: str, password: str, timeout: float = 15.0, default_from_name: str = '')`

Verstuurt tekstmails via één SMTP-account.

**Argumenten:**

- `host`: SMTP-server, bijv. `"smtp.gmail.com"`.
- `port`: Poort, bijv. 587 (STARTTLS).
- `username`: Het account, tevens afzenderadres.
- `password`: Wachtwoord; bij Gmail een app-wachtwoord.
- `timeout`: Seconden voordat een verbinding opgeeft.
- `default_from_name`: Weergavenaam als `send` er geen meekrijgt, bijv. de naam van de app.

##### `SmtpMailer.send(to: str, subject: str, body: str, reply_to: Optional[str] = None, from_name: Optional[str] = None) -> None`

Verstuur één tekstmail.

`From` is altijd het eigen account (Gmail staat geen ander adres
toe); alleen de weergavenaam verschilt, zoals "Henk via Bierkelder".
Antwoorden gaat naar `reply_to`.

**Argumenten:**

- `to`: Ontvanger.
- `subject`: Onderwerp.
- `body`: Tekst (platte tekst).
- `reply_to`: Optioneel antwoordadres.
- `from_name`: Optionele weergavenaam van de afzender.

**Fouten:**

- `MailError`: Verbinden, inloggen of versturen is mislukt.

## `security`

Beveiliging: tokens, inlogblokkade, redirects, captcha, sleutels en secrets.

### `security.captcha`

Eenvoudige robotcontrole voor openbare formulieren, zonder externe dienst.

Drie lagen, zonder sessie of database:

1. een rekensom, met het antwoord in een ondertekend token (itsdangerous);
2. een honeypot-veld dat mensen niet zien en bots wel invullen;
3. een tijdslot: niet te snel (bot) en niet te laat (verlopen) verzonden.

Gebruik: `create_challenge` bij het tonen van het formulier (zet de vraag
in beeld en het token in een verborgen veld, plus een verborgen leeg
honeypot-veld), en `verify_challenge` bij het verzenden. Teken met de
geheime sleutel van de app (bijv. Flask `secret_key`).

#### `MIN_SECONDS`

Constante, waarde: `3`

#### `MAX_SECONDS`

Constante, waarde: `7200`

#### `DEFAULT_SALT`

Constante, waarde: `'contact-captcha'`

#### `CaptchaError` (uitzondering, subklasse van `ValueError`)

Fout antwoord, of het token is ongeldig, te snel of verlopen.

De tekst is geschikt om aan de gebruiker te tonen.

#### `HoneypotTriggered` (uitzondering, subklasse van `Exception`)

Het verborgen veld is ingevuld: vrijwel zeker een bot.

Doe alsof het gelukt is (geen foutmelding), zodat de bot niets leert.

#### `Challenge(question: str, token: str)`

Een controlevraag.

**Velden:**

- `question`: De tekst voor de gebruiker, zoals "Hoeveel is 3 + 4?".
- `token`: Ondertekend token voor het verborgen formulierveld.

#### `create_challenge(secret_key: str, now: Optional[float] = None, rng: Optional[random.Random] = None, salt: str = DEFAULT_SALT) -> Challenge`

Maak een nieuwe controlevraag (som van twee getallen van 2 t/m 9).

**Argumenten:**

- `secret_key`: Geheime sleutel om het token te ondertekenen.
- `now`: Tijdstip (Unix-seconden); standaard nu. Voor tests.
- `rng`: Bron van willekeurige getallen; standaard `random.SystemRandom`. Voor tests.
- `salt`: Onderscheidt formulieren; gebruik per formulier een eigen salt.

**Geeft terug:**

Een `Challenge` met vraag en token.

#### `verify_challenge(secret_key: str, token: str, answer: str, honeypot: str, now: Optional[float] = None, salt: str = DEFAULT_SALT) -> None`

Controleer alle drie de lagen; geen uitzondering betekent: een mens.

**Argumenten:**

- `secret_key`: Dezelfde sleutel als bij `create_challenge`.
- `token`: Het token uit het verborgen veld.
- `answer`: Het antwoord van de gebruiker.
- `honeypot`: De inhoud van het honeypot-veld (hoort leeg te zijn).
- `now`: Tijdstip (Unix-seconden); standaard nu. Voor tests.
- `salt`: Dezelfde salt als bij `create_challenge`.

**Fouten:**

- `HoneypotTriggered`: Het honeypot-veld is ingevuld.
- `CaptchaError`: Ongeldig of vervalst token, binnen `MIN_SECONDS` of na `MAX_SECONDS` verzonden, of een fout antwoord.

### `security.lockout`

Inlogpogingen beperken: wanneer blokkeren, wanneer verplicht resetten.

Alleen de beslisregels, zonder database: de app slaat per account zelf het
aantal mislukte pogingen en `locked_until` op (in de database, niet in het
geheugen: serverless instanties delen geen geheugen) en vraagt na elke
mislukte poging `decide_after_failure` wat er moet gebeuren.

Standaardbeleid: na 3 fouten 15 minuten blokkeren, na nog eens 3 fouten
alleen nog inloggen na een nieuw wachtwoord via de mail. Een geslaagde login
zet de teller en `locked_until` terug.

Volgorde in de inlogfunctie van de app:

1. reset verplicht? weigeren;
2. `is_locked(locked_until, now)`? weigeren met `minutes_left`;
3. pas dan het wachtwoord controleren; fout? teller ophogen en
   `decide_after_failure` toepassen; goed? teller terugzetten.

#### `LockoutPolicy(max_attempts: int = 3, lockout_minutes: int = 15)`

Hoe streng inlogpogingen worden beperkt.

**Velden:**

- `max_attempts`: Fouten per ronde; na de eerste ronde volgt de blokkade, na de tweede de verplichte reset.
- `lockout_minutes`: Duur van de tijdelijke blokkade.

#### `DEFAULT_LOCKOUT_POLICY`

Constante, waarde: `LockoutPolicy()`

#### `LockoutAction` (enum: `WARN`, `LOCK`, `REQUIRE_RESET`)

Wat de app na een mislukte poging moet doen.

**Waarden:**

- `WARN`: Alleen melden, met het aantal resterende pogingen.
- `LOCK`: `locked_until` opslaan en de gebruiker laten wachten.
- `REQUIRE_RESET`: Account blokkeren tot er een nieuw wachtwoord is; mail de herstel-link.

#### `LockoutDecision(action: LockoutAction, attempts_left: int = 0, locked_until: Optional[datetime] = None, reset_follows: bool = False)`

De uitkomst van `decide_after_failure`.

**Velden:**

- `action`: Wat de app moet doen.
- `attempts_left`: Pogingen tot de volgende stap (alleen bij `WARN`).
- `locked_until`: Tot wanneer geblokkeerd (alleen bij `LOCK`).
- `reset_follows`: `True` als de volgende stap de verplichte reset is in plaats van de tijdelijke blokkade; handig voor de melding.

#### `decide_after_failure(failed_count: int, lock_already_used: bool, now: datetime, policy: LockoutPolicy = DEFAULT_LOCKOUT_POLICY) -> LockoutDecision`

Bepaal het gevolg van een mislukte inlogpoging.

**Argumenten:**

- `failed_count`: Het aantal mislukte pogingen, inclusief deze. Hoog het in de database atomair op (``UPDATE ... SET n = n + 1 RETURNING n``), zodat gelijktijdige pogingen goed tellen.
- `lock_already_used`: Of de tijdelijke blokkade al eens is gezet sinds de laatste geslaagde login (bijv. `locked_until is not None`). Zo wordt er nooit twee keer geblokkeerd.
- `now`: Het huidige moment, met tijdzone.
- `policy`: Het beleid.

**Geeft terug:**

Een `LockoutDecision`.

**Voorbeeld:**

```python
>>> from datetime import timezone
>>> now = datetime(2026, 1, 1, tzinfo=timezone.utc)
>>> decide_after_failure(1, False, now).attempts_left
2
>>> decide_after_failure(3, False, now).action
<LockoutAction.LOCK: 'lock'>
>>> decide_after_failure(6, True, now).action
<LockoutAction.REQUIRE_RESET: 'require_reset'>
```

#### `is_locked(locked_until: Optional[datetime], now: datetime) -> bool`

Geef aan of een account op dit moment tijdelijk geblokkeerd is.

**Argumenten:**

- `locked_until`: Het opgeslagen eindmoment, of `None`.
- `now`: Het huidige moment, met tijdzone.

**Geeft terug:**

`True` zolang `locked_until` in de toekomst ligt.

#### `minutes_left(locked_until: datetime, now: datetime) -> int`

Bereken de resterende wachttijd in hele minuten, naar boven afgerond.

**Argumenten:**

- `locked_until`: Het eindmoment van de blokkade.
- `now`: Het huidige moment.

**Geeft terug:**

Minimaal 1, zodat de melding nooit "0 minuten" zegt.

**Voorbeeld:**

```python
>>> from datetime import timezone
>>> now = datetime(2026, 1, 1, tzinfo=timezone.utc)
>>> minutes_left(now + timedelta(seconds=30), now)
1
```

### `security.redirects`

Veilig doorsturen: nooit naar een andere website (open redirect).

Gebruik dit voor elke redirect waarvan het doel van de gebruiker komt,
zoals `?next=/kelder` na het inloggen of de `Referer`-header.

#### `safe_next_path(target: Optional[str], fallback: str) -> str`

Geef `target` terug als het een pad binnen deze site is, anders `fallback`.

Toegestaan zijn alleen paden die met één `/` beginnen. `//evil.com`
(protocol-relatief), volledige URL's en backslashes worden geweigerd.

**Argumenten:**

- `target`: Het gevraagde doel, bijvoorbeeld de `next`-parameter.
- `fallback`: Waar je anders heen gaat, bijvoorbeeld het dashboard.

**Geeft terug:**

Een veilig pad.

**Voorbeeld:**

```python
>>> safe_next_path("/kelder?sort=naam", "/")
'/kelder?sort=naam'
>>> safe_next_path("//evil.example/login", "/")
'/'
```

#### `is_same_host_url(url: Optional[str], host: str) -> bool`

Geef aan of een volledige URL naar dezelfde host wijst.

**Argumenten:**

- `url`: Bijvoorbeeld `request.referrer`.
- `host`: De eigen host, bijvoorbeeld `request.host`.

**Geeft terug:**

`True` als de host (inclusief poort) precies overeenkomt.

**Voorbeeld:**

```python
>>> is_same_host_url("https://app.example/kelder", "app.example")
True
>>> is_same_host_url("https://evil.example/", "app.example")
False
```

### `security.secret_key`

Controle op de geheime sessiesleutel van een webapp.

Met een bekende of korte sleutel kan iedereen sessiecookies vervalsen en
zo als willekeurige gebruiker ingelogd raken. Roep
`ensure_production_secret_key` aan bij het opstarten.
Een goede sleutel maak je met `python -c "import secrets; print(secrets.token_hex(32))"`.

#### `DEV_SECRET_KEY_PLACEHOLDER`

Constante, waarde: `'dev-secret-change-me'`

#### `MIN_SECRET_KEY_LENGTH`

Constante, waarde: `32`

#### `InsecureSecretKeyError` (uitzondering, subklasse van `RuntimeError`)

De sleutel is in productie leeg, de standaardwaarde of te kort.

#### `ensure_production_secret_key(secret_key: str, is_production: bool, placeholder: str = DEV_SECRET_KEY_PLACEHOLDER, min_length: int = 32) -> None`

Weiger op te starten met een onveilige sleutel in productie.

Lokaal (`is_production=False`) mag alles, zodat ontwikkelen zonder
extra instellingen kan.

**Argumenten:**

- `secret_key`: De ingestelde sleutel.
- `is_production`: Of de app in productie draait (op Vercel bijv. `bool(os.environ.get("VERCEL"))`).
- `placeholder`: De bekende ontwikkelwaarde die nooit live mag.
- `min_length`: Minimale lengte in productie.

**Fouten:**

- `InsecureSecretKeyError`: In productie met een lege, standaard of te korte sleutel.

### `security.secrets_check`

Controle: staan er per ongeluk geheimen in bestanden die git bijhoudt?

Bewust geen "lijkt-op-een-sleutel"-scanner (te veel valse meldingen), maar
drie gerichte controles:

1. Worden de bestanden met echte geheimen (`.env` e.d.) door git genegeerd?
2. Staat een echte geheime waarde uit die bestanden letterlijk in een
   bestand dat git bijhoudt?
3. Staat er een PostgreSQL-verbindingsstring met wachtwoord in een
   bijgehouden bestand? Die hoort altijd uit een omgevingsvariabele te komen.

Laat `run_all_checks` meedraaien in de tests van elk project, dan gebeurt
de controle vanzelf vóór elke commit of deploy:

```python
def test_no_secrets_committed():
    findings = run_all_checks(SecretsCheckConfig(project_root=ROOT))
    assert not findings, "\n".join(findings)
```

#### `SecretsCheckConfig(project_root: Path, secret_files: Sequence[str] = ('.env', '.env.production', '.env.local'), secret_env_vars: Sequence[str] = ('DATABASE_URL', 'FLASK_SECRET_KEY', 'SMTP_PASSWORD', 'SUPABASE_STORAGE_KEY'), excluded_from_connection_string_check: Collection[str] = ('.env.example',), allowed_placeholders: Collection[str] = ('dev-secret-change-me',))`

Wat er per project gecontroleerd wordt.

**Velden:**

- `project_root`: De root van de git-repo.
- `secret_files`: Bestanden met echte geheimen, relatief aan de root.
- `secret_env_vars`: Namen van variabelen waarvan de waarde geheim is.
- `excluded_from_connection_string_check`: Bestanden die bewust een voorbeeld-verbindingsstring bevatten (zoals `.env.example`).
- `allowed_placeholders`: Waarden die geen lek zijn, ook al staan ze in een geheim bestand (zoals de ontwikkelsleutel).

#### `read_env_file(path: Path) -> dict[str, str]`

Lees een `.env`-bestand als `{naam: waarde}`.

Lege regels en regels die met `#` beginnen worden overgeslagen;
aanhalingstekens rond een waarde blijven staan.

**Argumenten:**

- `path`: Het bestand; bestaat het niet, dan komt er een leeg dict terug.

**Geeft terug:**

De variabelen uit het bestand.

#### `find_unignored_secret_files(config: SecretsCheckConfig) -> list[str]`

Meld geheime bestanden die bestaan maar níet door git worden genegeerd.

**Argumenten:**

- `config`: De projectinstellingen.

**Geeft terug:**

Eén melding per bestand dat bij een commit zou meegaan.

#### `find_hardcoded_secret_values(config: SecretsCheckConfig) -> list[str]`

Meld echte geheime waarden die letterlijk in een bijgehouden bestand staan.

Leest de waarden van `secret_env_vars` uit `secret_files` en zoekt
ze met `git grep`. Waarden korter dan 8 tekens en
`allowed_placeholders` tellen niet mee.

**Argumenten:**

- `config`: De projectinstellingen.

**Geeft terug:**

Eén melding per gelekte variabele, met de bestanden.

#### `find_hardcoded_connection_strings(config: SecretsCheckConfig) -> list[str]`

Meld bijgehouden bestanden met een PostgreSQL-verbindingsstring mét wachtwoord.

**Argumenten:**

- `config`: De projectinstellingen.

**Geeft terug:**

Eén melding per bestand.

#### `run_all_checks(config: SecretsCheckConfig) -> list[str]`

Voer alle drie de controles uit.

**Argumenten:**

- `config`: De projectinstellingen.

**Geeft terug:**

Alle meldingen; een lege lijst betekent: niets gevonden.

### `security.tokens`

Geheime tokens voor links in mails (uitnodigen, wachtwoord herstellen).

Patroon: maak met `new_token` een token, zet dat in de link en sla in de
database alleen `hash_token(token)` op. Lekt de database, dan zijn de links
daarmee niet te gebruiken. Bij het openen van de link zoek je op de hash.

#### `new_token(nbytes: int = 32) -> str`

Maak een onvoorspelbaar token dat veilig in een URL past.

**Argumenten:**

- `nbytes`: Aantal willekeurige bytes; 32 is ruim voldoende.

**Geeft terug:**

Een URL-veilige tekst van ongeveer `1.3 * nbytes` tekens.

**Voorbeeld:**

```python
>>> len(new_token()) >= 43
True
```

#### `hash_token(token: str) -> str`

Bereken de SHA-256-hash van een token, voor opslag in de database.

Voor willekeurige tokens is een snelle hash genoeg; wachtwoorden hash je
juist met een trage functie (`werkzeug.security`).

**Argumenten:**

- `token`: Het token uit de link.

**Geeft terug:**

64 hexadecimale tekens; past in een `VARCHAR(64)`.

**Voorbeeld:**

```python
>>> hash_token("abc")[:12]
'ba7816bf8f01'
```

## `storage`

Bestanden opslaan: afbeeldingen uploaden, lokaal of in Supabase Storage.

`supabase` vereist de extra `storage` (requests).

### `storage.images`

Geüploade afbeeldingen opslaan onder een willekeurige, unieke naam.

Lokaal (ontwikkelen) in een map, in productie via een opslagdienst zoals
`SupabaseStorageProvider`. De originele bestandsnaam van de gebruiker
wordt nooit gebruikt, alleen de extensie (na controle).

#### `DEFAULT_IMAGE_EXTENSIONS`

Constante, waarde: `{'gif', 'jpeg', 'jpg', 'png', 'webp'}`

#### `FileStorage` (protocol)

Een opslagdienst; bijvoorbeeld `SupabaseStorageProvider`.

##### `FileStorage.upload(filename: str, data: bytes, content_type: str) -> str`

Sla het bestand op en geef de publieke URL terug.

#### `InvalidImageError` (uitzondering, subklasse van `ValueError`)

Het bestandstype is niet toegestaan; de tekst noemt de toegestane typen.

#### `ImageUploadService(upload_folder: Optional[str] = None, storage_provider: Optional[FileStorage] = None, public_url_prefix: str = '/static/uploads', allowed_extensions: Collection[str] = DEFAULT_IMAGE_EXTENSIONS)`

Slaat afbeeldingen op via een opslagdienst of in een lokale map.

**Argumenten:**

- `upload_folder`: Lokale map (alleen gebruikt zonder `storage_provider`).
- `storage_provider`: Opslagdienst; heeft voorrang op de lokale map.
- `public_url_prefix`: URL-pad waaronder de lokale map bereikbaar is.
- `allowed_extensions`: Toegestane extensies, in kleine letters.

##### `ImageUploadService.save(filename: str, data: bytes, content_type: str) -> str`

Sla een afbeelding op onder een nieuwe UUID-naam.

**Argumenten:**

- `filename`: Originele bestandsnaam (alleen de extensie telt).
- `data`: De inhoud.
- `content_type`: MIME-type, bijv. `"image/jpeg"`.

**Geeft terug:**

De URL: van de opslagdienst, of `<public_url_prefix>/<naam>`.

**Fouten:**

- `InvalidImageError`: De extensie is niet toegestaan.
- `RuntimeError`: Er is geen opslagdienst en geen map ingesteld.

### `storage.supabase`

Bestanden uploaden naar Supabase Storage via de REST-API (zonder SDK).

Gebruik de `service_role`-key alleen op de server, nooit in de browser,
en commit hem nooit. De bucket moet publiek zijn als je de teruggegeven URL
direct in een `<img>` wilt gebruiken.

#### `SupabaseStorageError` (uitzondering, subklasse van `Exception`)

De Supabase Storage-API gaf een fout terug.

#### `SupabaseStorageProvider(base_url: str, service_role_key: str, bucket: str, timeout: float = 15.0)`

Uploadt bestanden naar één bucket.

**Argumenten:**

- `base_url`: De project-URL, bijv. `"https://xxxx.supabase.co"`.
- `service_role_key`: De `service_role`-key (Project Settings → API).
- `bucket`: Naam van de bucket, bijv. `"media"`.
- `timeout`: Seconden voordat een upload opgeeft.

##### `SupabaseStorageProvider.upload(filename: str, data: bytes, content_type: str) -> str`

Upload een bestand en geef de publieke URL terug.

Een bestaand bestand met dezelfde naam wordt overschreven (upsert);
geef dus unieke namen, bijvoorbeeld een UUID.

**Argumenten:**

- `filename`: Naam in de bucket.
- `data`: De inhoud.
- `content_type`: MIME-type, bijv. `"image/jpeg"`.

**Geeft terug:**

De publieke URL van het bestand.

**Fouten:**

- `SupabaseStorageError`: De API gaf een foutstatus.
- `requests.RequestException`: Netwerkfout of time-out.

## `validation`

Invoer controleren en normaliseren: e-mail, wachtwoord, barcode.

### `validation.barcode`

Barcodes (EAN-8, EAN-13, UPC) normaliseren.

Laat elke ingang (scanner, handmatige invoer, externe API, import) door
`normalize_barcode` gaan, zodat dezelfde barcode nooit als twee
verschillende waarden wordt opgeslagen.

#### `InvalidBarcodeError` (uitzondering, subklasse van `ValueError`)

De barcode is leeg of bevat iets anders dan cijfers.

#### `normalize_barcode(barcode: str) -> str`

Normaliseer een barcode naar een vergelijkbare tekst.

Witruimte rondom verdwijnt; leidende nullen blijven staan, want een
barcode is een code en geen getal.

**Argumenten:**

- `barcode`: De gescande of getypte barcode.

**Geeft terug:**

Alleen de cijfers, zonder witruimte rondom.

**Fouten:**

- `InvalidBarcodeError`: De barcode is leeg (of `None`) of bevat andere tekens dan cijfers.

**Voorbeeld:**

```python
>>> normalize_barcode(" 0012345 ")
'0012345'
```

### `validation.email`

E-mailadressen controleren en normaliseren.

Twee niveaus: alleen het formaat (bijvoorbeeld voor een contactformulier),
of het formaat plus een lijst toegestane domeinen (bijvoorbeeld bij
registratie, als drempel tegen wegwerpadressen). Beide geven het adres in
kleine letters en zonder witruimte terug, zodat je het zo kunt opslaan en
vergelijken.

#### `MAX_EMAIL_LENGTH`

Constante, waarde: `255`

#### `InvalidEmailError` (uitzondering, subklasse van `ValueError`)

Het e-mailadres is leeg, ongeldig of heeft een niet-toegestaan domein.

#### `normalize_email_format(email: str) -> str`

Controleer alleen het formaat van een e-mailadres en normaliseer het.

Bewust eenvoudig: precies één `@`, een punt in het domein, geen
witruimte en maximaal `MAX_EMAIL_LENGTH` tekens. Of het adres echt
bestaat, blijkt pas als je er een mail naartoe stuurt.

**Argumenten:**

- `email`: Het ingevulde adres, mag witruimte en hoofdletters bevatten.

**Geeft terug:**

Het adres in kleine letters, zonder witruimte rondom.

**Fouten:**

- `InvalidEmailError`: Het adres is leeg of heeft geen geldig formaat.

**Voorbeeld:**

```python
>>> normalize_email_format("  Henk@Example.COM ")
'henk@example.com'
```

#### `normalize_email(email: str, allowed_domains: Iterable[str], rejection_hint: str = '') -> str`

Controleer formaat én domein van een e-mailadres en normaliseer het.

**Argumenten:**

- `email`: Het ingevulde adres.
- `allowed_domains`: Domeinen die zijn toegestaan, zoals `{"gmail.com", "outlook.com"}`. Hoofdletters maken niet uit.
- `rejection_hint`: Optionele tekst achter de foutmelding bij een niet-toegestaan domein, zoals "Gebruik een Gmail-adres.".

**Geeft terug:**

Het adres in kleine letters, zonder witruimte rondom.

**Fouten:**

- `InvalidEmailError`: Het adres is leeg, ongeldig of het domein staat niet in `allowed_domains`.

**Voorbeeld:**

```python
>>> normalize_email("Henk@Gmail.com", {"gmail.com"})
'henk@gmail.com'
```

### `validation.password`

Wachtwoordbeleid: lengte, verplichte tekensoorten en een zwakke-lijst.

Het beleid is een `PasswordPolicy`; elke app kiest zijn eigen eisen of
gebruikt `DEFAULT_POLICY` (minimaal 10 tekens, met een hoofdletter, een
cijfer en een speciaal teken). Laat elke plek waar een wachtwoord wordt
gekozen (registreren, wijzigen, herstellen) door `validate_password` gaan.
Het hashen zelf hoort hier niet: gebruik daarvoor
`werkzeug.security.generate_password_hash` (scrypt).

#### `COMMON_WEAK_PASSWORDS`

Constante, waarde: `{'12345678', '123456789', '1234567890', 'iloveyou', 'letmein123', 'password', 'password1', 'qwertyuiop', 'wachtwoord', 'wachtwoord1', 'welkom123'}`

#### `PasswordPolicy(min_length: int = 10, require_uppercase: bool = True, require_digit: bool = True, require_special: bool = True, weak_passwords: frozenset[str] = COMMON_WEAK_PASSWORDS)`

De eisen waaraan een wachtwoord moet voldoen.

**Velden:**

- `min_length`: Minimaal aantal tekens.
- `require_uppercase`: Minstens één hoofdletter (ook À-Þ).
- `require_digit`: Minstens één cijfer.
- `require_special`: Minstens één teken dat geen letter of cijfer is.
- `weak_passwords`: Verboden wachtwoorden, in kleine letters; de vergelijking negeert hoofdletters.

#### `DEFAULT_POLICY`

Constante, waarde: `PasswordPolicy()`

#### `InvalidPasswordError` (uitzondering, subklasse van `ValueError`)

Het wachtwoord voldoet niet aan het beleid; de tekst zegt waarom.

#### `validate_password(password: str, policy: PasswordPolicy = DEFAULT_POLICY) -> None`

Controleer een wachtwoord tegen het beleid.

De controles lopen in vaste volgorde (lengte, zwakke-lijst, hoofdletter,
cijfer, speciaal teken) en de eerste die faalt bepaalt de melding, zodat
de gebruiker steeds één duidelijke opdracht krijgt.

**Argumenten:**

- `password`: Het gekozen wachtwoord.
- `policy`: Het beleid; standaard `DEFAULT_POLICY`.

**Fouten:**

- `InvalidPasswordError`: Het wachtwoord is te kort, staat op de zwakke-lijst of mist een verplichte tekensoort. De melding is geschikt om aan de gebruiker te tonen.

**Voorbeeld:**

```python
>>> validate_password("Correct1-Horse")  # geldig: geen uitzondering
>>> validate_password("kort", PasswordPolicy(min_length=12))
Traceback (most recent call last):
...
InvalidPasswordError: Wachtwoord moet minimaal 12 tekens lang zijn.
```

## `web`

Flask-hulpmiddelen: CSRF-bescherming en een veilige foutpagina.

Vereist de extra `web`: `pip install "general-standard-functions[web]"`.

### `web.csrf`

CSRF-bescherming voor alle formulieren van een Flask-app, zonder extra pakket.

Werking: per sessie één willekeurig token in de (ondertekende) Flask-sessie.
Elk formulier stuurt het mee als verborgen veld `csrf_token`. Bij elk
POST/PUT/PATCH/DELETE-verzoek worden beide vergeleken. Een andere website
kan het token niet lezen en dus geen formulier namens een ingelogde
gebruiker versturen.

Gebruik:

```python
init_csrf(app, fallback_endpoint="web.dashboard")
```

en zet in elk `<form method="post">` de regel `{{ csrf_field() }}`.
Zet daarnaast `SESSION_COOKIE_SAMESITE = "Lax"` en in productie
`SESSION_COOKIE_SECURE = True`. In tests kun je de controle uitzetten met
`app.config["CSRF_ENABLED"] = False`.

#### `FIELD_NAME`

Constante, waarde: `'csrf_token'`

#### `INVALID_TOKEN_MESSAGE`

Constante, waarde: `'Je sessie is verlopen of het formulier is ongeldig. Probeer het nog eens.'`

#### `get_csrf_token() -> str`

Geef het CSRF-token van de huidige sessie; maak er een als het er nog niet is.

**Geeft terug:**

Het token (ook beschikbaar in templates als `csrf_token()`).

#### `csrf_field() -> Markup`

Geef het verborgen formulierveld met het token.

**Geeft terug:**

`<input type="hidden" name="csrf_token" value="...">` als veilige
HTML; in templates `{{ csrf_field() }}`.

#### `init_csrf(app: Flask, fallback_endpoint: str) -> None`

Zet CSRF-controle aan voor alle onveilige verzoeken van de app.

Registreert `csrf_field` en `csrf_token` als Jinja-globals en een
`before_request`-controle. Bij een ontbrekend of fout token volgt een
flash-melding (`INVALID_TOKEN_MESSAGE`) en een redirect terug naar de
vorige pagina van deze site, of anders naar `fallback_endpoint`.

**Argumenten:**

- `app`: De Flask-app.
- `fallback_endpoint`: Endpoint om naartoe te sturen als de vorige pagina onbekend of van een andere site is, bijv. `"web.dashboard"`.

### `web.errors`

Een veilige foutpagina: de gebruiker ziet nooit SQL of een stacktrace.

Een onverwachte fout gaat met alle details naar de serverlog; de gebruiker
krijgt een vriendelijke pagina. Maak die template bij voorkeur zónder het
gewone basislayout, zodat hij ook werkt als de database de oorzaak is (een
layout die de ingelogde gebruiker of tellers ophaalt, faalt dan opnieuw).

#### `register_error_page(app: Flask, template: str, status: int = 500) -> None`

Toon `template` bij een fout met `status` en log de details.

Bij 500 vangt dit ook elke onverwachte uitzondering op (zolang
`PROPAGATE_EXCEPTIONS` uit staat, zoals in productie).

**Argumenten:**

- `app`: De Flask-app.
- `template`: De template, bijv. `"fout.html"`.
- `status`: De HTTP-status, standaard 500.

## Losse modules

### `i18n`

Vertaalhaak voor de meldingen van dit pakket (en van een app zelf).

De meldingen in dit pakket zijn Nederlands; dat is de brontekst. Zonder
verdere instellingen komt die tekst ongewijzigd terug, dus een app in één
taal hoeft niets te doen. Een meertalige app registreert één keer een
vertaalfunctie met `set_translator`, bijvoorbeeld de `gettext` en
`ngettext` van Flask-Babel; vanaf dan gaat elke melding daar doorheen.

Variabele delen staan als `%(naam)s` in de brontekst en worden pas ná het
vertalen ingevuld, zodat een vertaling ze op een andere plek in de zin kan
zetten. Een extractietool als `pybabel extract` vindt de teksten via de
namen `_`, `ngettext` en `N_`.

#### `Translator`

Constante, waarde: `collections.abc.Callable[[str], str]`

#### `PluralTranslator`

Constante, waarde: `collections.abc.Callable[[str, str, int], str]`

#### `set_translator(translator: Optional[Translator], plural_translator: Optional[PluralTranslator] = None) -> None`

Registreer de functies die een brontekst vertalen.

**Argumenten:**

- `translator`: Krijgt de brontekst (met `%(naam)s` er nog in) en geeft de vertaling terug. `None` zet het vertalen weer uit.
- `plural_translator`: Krijgt enkelvoud, meervoud en aantal en geeft de juiste vertaalde vorm terug. Zonder deze functie kiest `ngettext` zelf tussen de Nederlandse vormen.

**Voorbeeld:**

```python
>>> set_translator({"Hallo": "Hello"}.get)
>>> gettext("Hallo")
'Hello'
>>> set_translator(None)
>>> gettext("Hallo")
'Hallo'
```

#### `gettext(message: str, **params: object) -> str`

Vertaal `message` en vul daarna de variabelen in.

**Argumenten:**

- `message`: De Nederlandse brontekst, eventueel met `%(naam)s`.
- `**params`: De waarden voor de variabelen.

**Geeft terug:**

De vertaalde tekst met ingevulde variabelen; zonder vertaler de
brontekst zelf. Geeft de vertaler niets terug, dan ook de brontekst.

**Voorbeeld:**

```python
>>> gettext("Minimaal %(n)s tekens.", n=10)
'Minimaal 10 tekens.'
```

#### `ngettext(singular: str, plural: str, n: int, **params: object) -> str`

Vertaal een tekst met een enkelvoud en een meervoud.

**Argumenten:**

- `singular`: De Nederlandse tekst voor precies één.
- `plural`: De Nederlandse tekst voor nul of meer dan één.
- `n`: Het aantal; ook beschikbaar als `%(n)s` in de tekst.
- `**params`: Overige variabelen.

**Geeft terug:**

De juiste vorm, vertaald en met ingevulde variabelen.

**Voorbeeld:**

```python
>>> ngettext("%(n)s minuut", "%(n)s minuten", 1)
'1 minuut'
>>> ngettext("%(n)s minuut", "%(n)s minuten", 15)
'15 minuten'
```

#### `N_(message: str) -> str`

Markeer een tekst voor vertaling zonder hem nu te vertalen.

Voor vaste tabellen die bij het importeren al bestaan, zoals labels per
status: vertaal de waarde pas bij het tonen, met `gettext`.

**Voorbeeld:**

```python
>>> LABELS = {"open": N_("Openstaand")}
>>> gettext(LABELS["open"])
'Openstaand'
```

#### `_(message: str, **params: object) -> str`

Vertaal `message` en vul daarna de variabelen in.

**Argumenten:**

- `message`: De Nederlandse brontekst, eventueel met `%(naam)s`.
- `**params`: De waarden voor de variabelen.

**Geeft terug:**

De vertaalde tekst met ingevulde variabelen; zonder vertaler de
brontekst zelf. Geeft de vertaler niets terug, dan ook de brontekst.

**Voorbeeld:**

```python
>>> gettext("Minimaal %(n)s tekens.", n=10)
'Minimaal 10 tekens.'
```

### `localtime`

Tijdstippen opslaan in UTC en tonen in lokale (standaard Nederlandse) tijd.

Afspraak: in de database staat altijd UTC (`TIMESTAMPTZ`). Pas bij het
tonen zet je om naar lokale tijd, en wat de gebruiker invult zet je terug
naar UTC. Zomer- en wintertijd gaan dan vanzelf goed. Alle functies hebben
een `tz`-argument; standaard is dat `DEFAULT_TIMEZONE` (Europe/Amsterdam).

#### `DEFAULT_TIMEZONE`

Constante, waarde: `zoneinfo.ZoneInfo(key='Europe/Amsterdam')`

#### `EMPTY_PLACEHOLDER`

Constante, waarde: `'—'`

#### `to_local(value: Optional[datetime], tz: tzinfo = DEFAULT_TIMEZONE) -> Optional[datetime]`

Zet een tijdstip om naar lokale tijd.

**Argumenten:**

- `value`: Het tijdstip; zonder tijdzone ("naive") geldt het als UTC, omdat de database in UTC opslaat.
- `tz`: De doeltijdzone.

**Geeft terug:**

Hetzelfde moment in `tz`, of `None` als `value` `None` is.

**Voorbeeld:**

```python
>>> to_local(datetime(2026, 7, 1, 18, 0)).hour
20
```

#### `format_local(value: Optional[datetime], fmt: str = '%Y-%m-%d %H:%M', tz: tzinfo = DEFAULT_TIMEZONE) -> str`

Formatteer een tijdstip in lokale tijd, geschikt als Jinja-filter.

**Argumenten:**

- `value`: Het tijdstip (naive = UTC).
- `fmt`: `strftime`-formaat.
- `tz`: De tijdzone waarin je het wilt tonen.

**Geeft terug:**

De opgemaakte tekst, of `EMPTY_PLACEHOLDER` ("—") als er geen
tijdstip is.

**Voorbeeld:**

```python
>>> format_local(datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc))
'2026-01-15 19:00'
```

#### `format_local_nl(value: Optional[datetime], with_time: bool = True, tz: tzinfo = DEFAULT_TIMEZONE) -> str`

Formatteer een tijdstip met Nederlandse dag- en maandnamen.

Werkt los van de taalinstelling (locale) van de server.

**Argumenten:**

- `value`: Het tijdstip (naive = UTC).
- `with_time`: Ook uren en minuten tonen.
- `tz`: De tijdzone waarin je het wilt tonen.

**Geeft terug:**

Bijvoorbeeld "za 14 nov 2026, 20:00", of "—" als er geen tijdstip is.

**Voorbeeld:**

```python
>>> format_local_nl(datetime(2026, 11, 14, 19, 0, tzinfo=timezone.utc))
'za 14 nov 2026, 20:00'
```

#### `InvalidLocalDatetimeError` (uitzondering, subklasse van `ValueError`)

Er is geen geldige datum/tijd ingevuld.

#### `parse_local_datetime(text: str, tz: tzinfo = DEFAULT_TIMEZONE) -> datetime`

Lees een ingevulde lokale datum/tijd en geef UTC terug voor opslag.

Bedoeld voor de waarde van `<input type="datetime-local">`, zoals
"2026-11-14T20:00". Bevat de tekst al een tijdzone, dan wordt die
gerespecteerd.

**Argumenten:**

- `text`: De ingevulde datum/tijd (ISO 8601).
- `tz`: De tijdzone waarin de gebruiker denkt.

**Geeft terug:**

Het moment in UTC, met tijdzone.

**Fouten:**

- `InvalidLocalDatetimeError`: Leeg of geen geldig formaat.

**Voorbeeld:**

```python
>>> parse_local_datetime("2026-11-14T20:00")
datetime.datetime(2026, 11, 14, 19, 0, tzinfo=datetime.timezone.utc)
```
