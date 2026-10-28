"""Geüploade afbeeldingen opslaan onder een willekeurige, unieke naam.

Lokaal (ontwikkelen) in een map, in productie via een opslagdienst zoals
``SupabaseStorageProvider``. De originele bestandsnaam van de gebruiker
wordt nooit gebruikt, alleen de extensie (na controle). Met ``delete`` gaat
een eigen upload weer weg, bijvoorbeeld als een gebruiker zijn account
verwijdert.
"""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import Collection
from typing import Optional, Protocol

from general_standard_functions.i18n import _

__all__ = ["DEFAULT_IMAGE_EXTENSIONS", "FileStorage", "InvalidImageError", "ImageUploadService"]

DEFAULT_IMAGE_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "gif", "webp"})


# Alleen namen zoals ``save`` ze maakt; zo kan ``delete`` nooit buiten de
# eigen opslag of map komen.
_STORED_NAME_RE = re.compile(r"^[0-9a-f]{32}\.[a-z0-9]{1,5}$")


class FileStorage(Protocol):
    """Een opslagdienst; bijvoorbeeld ``SupabaseStorageProvider``."""

    public_prefix: str

    def upload(self, filename: str, data: bytes, content_type: str) -> str:
        """Sla het bestand op en geef de publieke URL terug."""

    def delete(self, filename: str) -> None:
        """Verwijder het bestand; een al verwijderd bestand is geen fout."""


class InvalidImageError(ValueError):
    """Het bestandstype is niet toegestaan; de tekst noemt de toegestane typen."""


class ImageUploadService:
    """Slaat afbeeldingen op via een opslagdienst of in een lokale map.

    Args:
        upload_folder: Lokale map (alleen gebruikt zonder ``storage_provider``).
        storage_provider: Opslagdienst; heeft voorrang op de lokale map.
        public_url_prefix: URL-pad waaronder de lokale map bereikbaar is.
        allowed_extensions: Toegestane extensies, in kleine letters.
    """

    def __init__(
        self,
        upload_folder: Optional[str] = None,
        storage_provider: Optional[FileStorage] = None,
        public_url_prefix: str = "/static/uploads",
        allowed_extensions: Collection[str] = DEFAULT_IMAGE_EXTENSIONS,
    ) -> None:
        self._upload_folder = upload_folder
        self._storage_provider = storage_provider
        self._public_url_prefix = public_url_prefix.rstrip("/")
        self._allowed_extensions = frozenset(allowed_extensions)

    def save(self, filename: str, data: bytes, content_type: str) -> str:
        """Sla een afbeelding op onder een nieuwe UUID-naam.

        Args:
            filename: Originele bestandsnaam (alleen de extensie telt).
            data: De inhoud.
            content_type: MIME-type, bijv. ``"image/jpeg"``.

        Returns:
            De URL: van de opslagdienst, of ``<public_url_prefix>/<naam>``.

        Raises:
            InvalidImageError: De extensie is niet toegestaan.
            RuntimeError: Er is geen opslagdienst en geen map ingesteld.
        """
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in self._allowed_extensions:
            raise InvalidImageError(
                _("Afbeelding moet een van deze typen zijn: %(types)s",
                  types=", ".join(sorted(self._allowed_extensions)))
            )

        stored_name = f"{uuid.uuid4().hex}.{extension}"

        if self._storage_provider is not None:
            return self._storage_provider.upload(stored_name, data, content_type)

        if self._upload_folder is None:
            raise RuntimeError("Geen opslaglocatie ingesteld voor afbeeldingen.")
        with open(os.path.join(self._upload_folder, stored_name), "wb") as fh:
            fh.write(data)
        return f"{self._public_url_prefix}/{stored_name}"

    def delete(self, url: Optional[str]) -> bool:
        """Verwijder een afbeelding die eerder met ``save`` is opgeslagen.

        Een URL van ergens anders (bijvoorbeeld een productfoto van een
        externe bron) wordt nooit aangeraakt.

        Args:
            url: De URL zoals ``save`` die teruggaf; ``None`` mag ook.

        Returns:
            True als het een eigen upload was en die is verwijderd.

        Raises:
            Fouten van de opslagdienst, zoals ``SupabaseStorageError``.

        Example:
            >>> ImageUploadService(upload_folder="/tmp").delete("https://elders.example/foto.jpg")
            False
        """
        if not url:
            return False
        name = url.rsplit("/", 1)[-1]
        if not _STORED_NAME_RE.match(name):
            return False
        if self._storage_provider is not None:
            if not url.startswith(self._storage_provider.public_prefix):
                return False
            self._storage_provider.delete(name)
            return True
        if self._upload_folder is None or not url.startswith(f"{self._public_url_prefix}/"):
            return False
        path = os.path.join(self._upload_folder, name)
        if os.path.exists(path):
            os.remove(path)
        return True
