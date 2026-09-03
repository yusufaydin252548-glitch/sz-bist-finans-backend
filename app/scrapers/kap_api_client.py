"""KAP resmi API istemcisi — MKK API Portal (apiportal.mkk.com.tr).

KAP Veri Yayin Servisleri'ne resmi, sozlesmeli erisim. Eski
`kap_scraper.py` www.kap.org.tr HTML'ini kaziyor; bu modul onun yerini
alacak resmi kaynaktir.

Dogrulanmis davranis (test/dev gateway — apigwdev.mkk.com.tr/api/vyk)
------------------------------------------------------------------------
Auth : Authorization: Basic base64(CLIENT_ID:CLIENT_SECRET)
       (test ortaminda token gerekmez; canli ortam Bearer token ister)

  GET /lastDisclosureIndex
      -> {"lastDisclosureIndex": "1231017"}

  GET /members
      -> [{"id","title","stockCode","memberType","kfifUrl"}, ...]
         (sektor bilgisi YOK)

  GET /disclosures?disclosureIndex=N            (param zorunlu)
      -> [{"disclosureIndex","disclosureType","disclosureClass",
           "subReportIds","title","companyId","acceptedDataFileTypes"}]

  GET /disclosureDetail/{index}?fileType=html   (path + param zorunlu)
      fileType, /disclosures yanitindaki acceptedDataFileTypes'tan biri.
      -> {"disclosureIndex","senderTitle","subject":{"tr","en"},
          "relatedStocks","summary","time","link","attachmentUrls",
          "htmlMessages":[{"id","tr","en"}]}   # tr/en alanlari base64 HTML

Ucretsiz plan: 6 istek / dakika (asilinca HTTP 429, faultCode ERR-224).

TEYIT bekleyen (portal Documentation'dan): canli gateway host, canli
token endpoint + generateToken sozlesmesi, memberDetail / funds /
memberSecurities / blockedDisclosures / caEventStatus imzalari.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Iterable, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Servis yollari. {index} olanlar path parametresi alir.
_ENDPOINTS: dict[str, str] = {
    "last_disclosure_index": "/lastDisclosureIndex",
    "disclosures":           "/disclosures",
    "disclosure_detail":     "/disclosureDetail/{index}",
    "members":               "/members",
    "member_detail":         "/memberDetail/{id}",
    "member_securities":     "/memberSecurities/{id}",
    "funds":                 "/funds",
    "fund_detail":           "/fundDetail/{id}",
    "blocked_disclosures":   "/blockedDisclosures",
    "ca_event_status":       "/caEventStatus",
}

_TOKEN_FALLBACK_TTL = 3000
_TOKEN_SKEW = 60


class KAPApiError(RuntimeError):
    """KAP API cagrisi basarisiz oldu."""


class KAPThrottled(KAPApiError):
    """Ucretsiz plan istek limiti asildi (HTTP 429)."""


def _as_list(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "content", "items", "result", "disclosures"):
            if isinstance(payload.get(key), list):
                return payload[key]
        return [payload]
    return []


def decode_html_message(value: str) -> str:
    """htmlMessages[].tr / .en alanindaki base64 icerigi cozer.

    Icerik ISO-8859-9 (Latin-5) kodlu XHTML olabilir; once utf-8 denenir.
    """
    raw = base64.b64decode(value)
    for enc in ("utf-8", "iso-8859-9", "cp1254"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


class KAPApiClient:
    """MKK API Portal uzerinden KAP Veri Yayin Servisleri istemcisi."""

    def __init__(self, settings=None, *, client: Optional[httpx.AsyncClient] = None):
        self.settings = settings or get_settings()

        base = (self.settings.KAP_API_BASE_URL or "").rstrip("/")
        prefix = (self.settings.KAP_API_PREFIX or "").strip("/")
        self._base = f"{base}/{prefix}" if prefix else base
        if not base:
            raise KAPApiError("KAP_API_BASE_URL bos — .env'de tanimla.")

        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=30.0,
            headers={"Accept": "application/json"},
            follow_redirects=True,
        )
        self._token: Optional[str] = None
        self._token_exp: float = 0.0

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def __aenter__(self) -> "KAPApiClient":
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.close()

    # -- kimlik dogrulama --------------------------------------------------

    async def _auth_headers(self) -> dict[str, str]:
        if self.settings.KAP_API_USE_TOKEN:
            return {"Authorization": f"Bearer {await self._get_token()}"}

        ck = self.settings.KAP_API_CLIENT_ID
        cs = self.settings.KAP_API_CLIENT_SECRET
        if not (ck and cs):
            raise KAPApiError(
                "KAP_API_CLIENT_ID / KAP_API_CLIENT_SECRET bos — .env'de tanimla."
            )
        creds = base64.b64encode(f"{ck}:{cs}".encode()).decode()
        return {"Authorization": f"Basic {creds}"}

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_exp - _TOKEN_SKEW:
            return self._token

        url = self.settings.KAP_API_TOKEN_URL
        if not url:
            raise KAPApiError(
                "KAP_API_USE_TOKEN=True ama KAP_API_TOKEN_URL bos. "
                "Canli generateToken endpoint'ini portaldan al."
            )
        # TEYIT: govde + yanit alan adlari canli generateToken sozlesmesine gore.
        payload = {
            "clientId": self.settings.KAP_API_CLIENT_ID,
            "clientSecret": self.settings.KAP_API_CLIENT_SECRET,
        }
        try:
            resp = await self.client.post(url, json=payload)
            self._raise_for_status(resp, "generateToken")
            data = resp.json()
        except httpx.HTTPError as exc:
            raise KAPApiError(f"generateToken cagrisi basarisiz: {exc}") from exc

        token = data.get("token") or data.get("access_token") or data.get("accessToken")
        if not token:
            raise KAPApiError(f"generateToken yaniti beklenmedik: {data}")
        ttl = data.get("expiresIn") or data.get("expires_in") or _TOKEN_FALLBACK_TTL
        self._token, self._token_exp = token, time.time() + float(ttl)
        logger.info("KAP API token yenilendi (ttl=%ss)", ttl)
        return token

    # -- alt seviye istek --------------------------------------------------

    @staticmethod
    def _raise_for_status(resp: httpx.Response, label: str) -> None:
        if resp.status_code == 429:
            raise KAPThrottled(f"{label}: istek limiti asildi (6/dk). HTTP 429")
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = " ".join(resp.text.split())[:400]
            if resp.status_code in (401, 403):
                logger.error(
                    "KAP API yetki hatasi (%s) @ %s — CLIENT_ID/SECRET, "
                    "KAP_API_USE_TOKEN veya IP whitelist kontrol et. %s",
                    resp.status_code, label, body,
                )
            else:
                logger.error("KAP API %s @ %s — %s", resp.status_code, label, body)
            raise KAPApiError(f"{label}: HTTP {resp.status_code} — {body}") from exc

    async def _get(
        self,
        key: str,
        *,
        path_params: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> Any:
        path = _ENDPOINTS[key].format(**(path_params or {}))
        headers = await self._auth_headers()
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            resp = await self.client.get(self._base + path, params=clean or None, headers=headers)
            self._raise_for_status(resp, key)
            return resp.json()
        except KAPApiError:
            raise
        except httpx.HTTPError as exc:
            raise KAPApiError(f"{key}: baglanti hatasi — {exc}") from exc

    # -- servisler --------------------------------------------------

    async def last_disclosure_index(self) -> int:
        """lastDisclosureIndex — yayinlanmis son bildirim id'si.

        Artimli senkron icin ust sinir.
        """
        data = await self._get("last_disclosure_index")
        if isinstance(data, dict):
            val = data.get("lastDisclosureIndex") or data.get("disclosureIndex")
            if val is not None:
                return int(val)
            raise KAPApiError(f"lastDisclosureIndex yaniti beklenmedik: {data}")
        return int(data)

    async def disclosure(self, disclosure_index: int | str) -> Optional[dict]:
        """disclosures?disclosureIndex=N — tek bildirimin ozet kaydi.

        Yanit: disclosureType, disclosureClass, subReportIds, title,
        companyId, acceptedDataFileTypes. Bulunamazsa None.
        """
        rows = _as_list(
            await self._get("disclosures", params={"disclosureIndex": disclosure_index})
        )
        return rows[0] if rows else None

    async def disclosures(
        self, indices: Iterable[int | str]
    ) -> list[dict]:
        """Birden fazla index icin disclosure ozet kaydi (sirali cagri).

        Ucretsiz planda 6/dk limit oldugu icin cagiran taraf araya
        bekleme koymali. KAPThrottled firlarsa yakalayip beklet.
        """
        out: list[dict] = []
        for idx in indices:
            row = await self.disclosure(idx)
            if row:
                out.append(row)
        return out

    async def disclosure_detail(
        self, disclosure_index: int | str, file_type: str = "html"
    ) -> dict:
        """disclosureDetail/{index}?fileType=... — tam bildirim icerigi.

        `file_type`, ilgili disclosure'in acceptedDataFileTypes listesinden
        biri olmali (genelde "html"). htmlMessages[].tr/.en base64'tur —
        `decode_html_message()` ile coz.
        """
        data = await self._get(
            "disclosure_detail",
            path_params={"index": disclosure_index},
            params={"fileType": file_type},
        )
        if isinstance(data, list):
            return data[0] if data else {}
        return data

    async def members(self) -> list[dict]:
        """members — sirket listesi (id, title, stockCode, memberType, kfifUrl).

        NOT: sektor bilgisi icermez.
        """
        return _as_list(await self._get("members"))

    # --- asagidakiler portal Documentation'dan teyit edilmedi ---

    async def member_detail(self, member_id: str) -> dict:
        data = await self._get("member_detail", path_params={"id": member_id})
        return data[0] if isinstance(data, list) and data else (data or {})

    async def member_securities(self, member_id: str) -> list[dict]:
        return _as_list(await self._get("member_securities", path_params={"id": member_id}))

    async def funds(self) -> list[dict]:
        return _as_list(await self._get("funds"))

    async def fund_detail(self, fund_id: str) -> dict:
        data = await self._get("fund_detail", path_params={"id": fund_id})
        return data[0] if isinstance(data, list) and data else (data or {})

    async def blocked_disclosures(self) -> list[dict]:
        return _as_list(await self._get("blocked_disclosures"))

    async def ca_event_status(self) -> list[dict]:
        return _as_list(await self._get("ca_event_status"))
