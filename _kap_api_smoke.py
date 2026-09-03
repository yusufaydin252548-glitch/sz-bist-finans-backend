"""KAP resmi API duman testi.

    python _kap_api_smoke.py

.env icinde KAP_API_CLIENT_ID + KAP_API_CLIENT_SECRET dolu olmali.
Ucretsiz plan 6 istek/dk oldugu icin cagrilar arasinda beklenir.

Akis: lastDisclosureIndex -> disclosures(index) -> disclosureDetail -> members
"""

import asyncio
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.scrapers.kap_api_client import (
    KAPApiClient,
    KAPApiError,
    KAPThrottled,
    decode_html_message,
)

PAUSE = 12  # saniye — 6/dk limitine takilmamak icin


async def main() -> None:
    async with KAPApiClient() as kap:
        print("BASE URL :", kap._base)
        print("AUTH     :", "Bearer token" if kap.settings.KAP_API_USE_TOKEN else "Basic (CK:CS)")
        print("-" * 60)

        try:
            idx = await kap.last_disclosure_index()
            print(f"lastDisclosureIndex : {idx}")
            await asyncio.sleep(PAUSE)

            row = await kap.disclosure(idx)
            print(f"disclosure({idx})    : {row}")
            await asyncio.sleep(PAUSE)

            if row and row.get("acceptedDataFileTypes"):
                ft = row["acceptedDataFileTypes"][0]
                detail = await kap.disclosure_detail(idx, file_type=ft)
                subj = detail.get("subject")
                print(f"disclosureDetail    : subject={subj} time={detail.get('time')}")
                msgs = detail.get("htmlMessages") or []
                if msgs and msgs[0].get("tr"):
                    html = decode_html_message(msgs[0]["tr"])
                    print(f"  html[0] ({len(html)} char): {html[:120]!r}")
                await asyncio.sleep(PAUSE)

            members = await kap.members()
            print(f"members             : {len(members)} sirket")
            for m in members[:3]:
                print("   -", m)

        except KAPThrottled as exc:
            print(f"THROTTLE: {exc} — 60 sn bekleyip tekrar dene")
        except KAPApiError as exc:
            print(f"HATA: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
