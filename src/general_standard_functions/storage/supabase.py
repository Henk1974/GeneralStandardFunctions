"""Bestanden uploaden naar en verwijderen uit Supabase Storage via de
REST-API (zonder SDK).

Gebruik de ``service_role``-key alleen op de server, nooit in de browser,
en commit hem nooit. De bucket moet publiek zijn als je de teruggegeven URL
direct in een ``<img>`` wilt gebruiken.
"""

from __future__ import annotations

import requests

__all__ = ["SupabaseStorageError", "SupabaseStorageProvider"]


class SupabaseStorageError(Exception):
    """De Supabase Storage-API gaf een fout terug."""


class SupabaseStorageProvider:
    """Uploadt bestanden naar één bucket.

    Args:
        base_url: De project-URL, bijv. ``"https://xxxx.supabase.co"``.
        service_role_key: De ``service_role``-key (Project Settings → API).
        bucket: Naam van de bucket, bijv. ``"media"``.
        timeout: Seconden voordat een upload opgeeft.
    """

    def __init__(self, base_url: str, service_role_key: str, bucket: str, timeout: float = 15.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_role_key = service_role_key
        self._bucket = bucket
        self._timeout = timeout

    def upload(self, filename: str, data: bytes, content_type: str) -> str:
        """Upload een bestand en geef de publieke URL terug.

        Een bestaand bestand met dezelfde naam wordt overschreven (upsert);
        geef dus unieke namen, bijvoorbeeld een UUID.

        Args:
            filename: Naam in de bucket.
            data: De inhoud.
            content_type: MIME-type, bijv. ``"image/jpeg"``.

        Returns:
            De publieke URL van het bestand.

        Raises:
            SupabaseStorageError: De API gaf een foutstatus.
            requests.RequestException: Netwerkfout of time-out.
        """
        response = requests.post(
            f"{self._base_url}/storage/v1/object/{self._bucket}/{filename}",
            data=data,
            headers={
                "Authorization": f"Bearer {self._service_role_key}",
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            timeout=self._timeout,
        )
        if response.status_code >= 300:
            raise SupabaseStorageError(
                f"Upload naar Supabase Storage mislukt ({response.status_code}): {response.text}"
            )
        return f"{self.public_prefix}{filename}"

    @property
    def public_prefix(self) -> str:
        """Begin van elke publieke URL in deze bucket, eindigt op ``/``.

        Example:
            >>> SupabaseStorageProvider("https://p.supabase.co", "key", "media").public_prefix
            'https://p.supabase.co/storage/v1/object/public/media/'
        """
        return f"{self._base_url}/storage/v1/object/public/{self._bucket}/"

    def delete(self, filename: str) -> None:
        """Verwijder een bestand uit de bucket. Bestaat het niet (meer), dan
        is dat geen fout: het doel, weg zijn, is dan al bereikt.

        Args:
            filename: Naam in de bucket.

        Raises:
            SupabaseStorageError: De API gaf een andere foutstatus.
            requests.RequestException: Netwerkfout of time-out.
        """
        response = requests.delete(
            f"{self._base_url}/storage/v1/object/{self._bucket}/{filename}",
            headers={"Authorization": f"Bearer {self._service_role_key}"},
            timeout=self._timeout,
        )
        if response.status_code >= 300 and response.status_code not in (400, 404):
            raise SupabaseStorageError(
                f"Verwijderen uit Supabase Storage mislukt ({response.status_code}): {response.text}"
            )
