# Faz 1: Sub-Agent Tabanlı İçerik Motoru (MVP)

**Öncelik:** İlk faz — proje bu fazla başlayacak

---

## 1. Ne yapacak?
- Her gün düzenli olarak halka açık BIST şirketleriyle ilgili haber/bildirim çekilecek
- İçerikler sektörlere ayrılacak (bankacılık, enerji, sanayi, teknoloji, perakende vb.)
- Sub-agent'lar bu ham veriyi işleyip blog formatında yazılara dönüştürecek
- İleride gerçek kullanıcı ve gerçek ekonomist yazıları da bu akışa entegre olacak

---

## 2. Uçtan Uca Veri Akışı (İki Paralel Yol)

Artık iki geliştirme yolu var — biri hemen kullanılabilir (MVP), diğeri resmi/production (sözleşme sonrası):

### Yol A — MVP/Geliştirme (şimdi kullanılabilir, borsapy ile)
```
1. bp.Ticker(symbol).news        → KAP bildirimlerini doğrudan çek (borsapy sarmalıyor)
2. bp.Ticker(symbol).calendar    → beklenen açıklamalar
3. bp.sectors() / info["sector"] → sektör eşleştirme (aynı kütüphaneden, ekstra kaynağa gerek yok)
4. LLM sub-agent zinciri         → özetle, yaz, kalite kontrolden geçir
5. Yayınla (kapalı/test modunda) → henüz gerçek kullanıcıya açılmadan
```
Avantajı: MKK production sözleşmesi beklemeden, tek kütüphaneyle (borsapy) hem haber hem sektör hem fiyat verisi gelir — mimari çok basitleşir. Dezavantajı: borsapy'nin kendi "kişisel/eğitim amaçlı" lisans kısıtı geçerli (bkz. §6.3), muhtemelen KAP verisini kendisi de scraping ile alıyor.

### Yol B — Production/Resmi (sözleşme sonrası, MKK KAP API ile)
```
1. lastDisclosureIndex  → bugüne kadarki en güncel bildirim index'ini al
2. disclosures           → o index'ten itibaren bildirim listesini (title, companyId, subReportIds) çek
3. disclosureDetail       → her bildirimin subReportIds'i ile tam içeriği (Base64+HTML) çek
4. Decode & Parse         → Base64 çöz, HTML'den düz metni çıkar
5. members (+ BIST sektör verisi) → şirketi sektöre eşleştir (companyId/stockCode üzerinden)
6. LLM sub-agent zinciri  → özetle, yaz, kalite kontrolden geçir
7. Yayınla (gerçek kullanıcılara açık) → PostgreSQL + Next.js frontend'e yaz
```
Bu akış tamamen test edildi ve çalışıyor (bkz. §6.1), ama **gerçek kullanıcılara içerik göstermek için** şirket kuruluşu + Borsa İstanbul Veri Yayın Sözleşmesi şart (bkz. §6.1.4).

**Strateji:** Şimdi Yol A ile MVP'yi tamamen geliştir ve kapalı/test modunda çalıştır. Yol B'nin kod altyapısı zaten hazır (Claude Code'da `KAPApiClient`). Şirket + sözleşme süreci tamamlanınca, veri kaynağını Yol A'dan Yol B'ye geçirip gerçek kullanıcılara aç.

---

## 3. Sub-Agent Mimarisi

Çok sayıda sub-agent olacağı belirtildiği için hiyerarşik/rol bazlı bir yapı öneriliyor. Roller, iki yola da uyacak şekilde soyutlandı (veri kaynağı Yol A/B arasında değişse de agent yapısı aynı kalır):

| Agent Rolü | Görev | Girdi | Çıktı |
|---|---|---|---|
| **Orkestratör** | Rate limit'e uygun şekilde tüm zinciri tetikler, hata/backoff yönetir | Zamanlayıcı (cron) | İş kuyruğuna görevler |
| **Kaynak Tarayıcı Agent** | Yeni bildirimleri tespit eder — **Yol A:** `Ticker.news`, **Yol B:** `lastDisclosureIndex`+`disclosures` | Son işlenen tarih/index | Bildirim listesi (başlık, şirket, kaynak ID) |
| **Detay Çekici Agent** | Tam bildirim içeriğini çeker (Yol B'de ayrı adım; Yol A'da `news` zaten içerik döndürebilir) | Bildirim referansı | Ham içerik |
| **Ayrıştırıcı (Parser) Agent** | Gerekirse Base64 çözer, HTML'den düz metin çıkarır (Yol B için) | Ham içerik | Temiz metin + meta veri |
| **Sektör Eşleştirici Agent** | Şirketi sektöre eşleştirir — her iki yolda da `borsapy` (`bp.sectors()`, `info["sector"]`) kullanılıyor | companyId/stockCode | Sektör etiketi |
| **Analiz/Özetleyici Agent** | Temiz metni bağlamsallaştırır (ör. "bu sermaye artırımı ne anlama geliyor") | Temiz metin | Analiz notları |
| **Yazar (Writer) Agent** | Blog formatında, SEO uyumlu yazı üretir (Claude API) | Temiz metin + analiz + sektör | Taslak blog yazısı |
| **Çeviri/Lokalizasyon Agent** | İçeriği İngilizce'ye çevirir (bkz. §6.2) | TR taslak | EN taslak |
| **Editör/Kalite Kontrol Agent** | Otomatik doğrulama: sayısal verileri kaynakla çapraz kontrol eder, halüsinasyon riskini azaltır, yayına onaylar | Taslak (TR+EN) | Onaylı/reddedilmiş içerik |
| **Yayıncı Agent** | Onaylanan içeriği veritabanına yazar, zamanlar (Yol A'da: kapalı/test modu; Yol B'de: herkese açık) | Onaylı içerik | Yayınlanmış yazı |

> Not: Kaynak Tarayıcı ve Detay Çekici agent'larının veri kaynağı soyutlanmış olmalı (ör. bir `DisclosureSource` interface'i, hem `BorsapySource` hem `KAPApiSource` implementasyonu) — böylece Yol A'dan Yol B'ye geçiş, sadece bir konfigürasyon değişikliği olur, mimari yeniden yazılmaz.

---

## 4. Veri Kaynakları (araştırıldı)

| Kaynak | Ne sağlıyor | Not |
|---|---|---|
| **KAP (Kamuyu Aydınlatma Platformu) REST API** | Resmi şirket bildirimleri: özel durum açıklamaları, finansal raporlar, sermaye artırımı, temettü, birleşme/devralma vb. `disclosures`, `disclosureDetail`, `downloadAttachment`, `lastDisclosureIndex`, `members` servisleri mevcut | En güvenilir/resmi kaynak (**Yol B**). Şirket kuruluşu + Borsa İstanbul Veri Yayın Sözleşmesi gerektiriyor — bkz. §6.1.4 |
| **borsapy (açık kaynak Python kütüphanesi)** | BIST hisse, döviz, kripto, fon verisi; TradingView WebSocket üzerinden gerçek zamanlı fiyat/OHLCV akışı; 53 sektörün tam listesi + hisse bazlı sektör eşleştirme; **`Ticker.news`/`calendar`/`earnings_dates` ile doğrudan KAP bildirimleri**; `screen_stocks()` ile 40+ kriterli tarama; `EVDS()` ile TCMB'nin 145 kategorilik ücretsiz makro veri API'si | ⚠️ **Ticari kullanım yasak** (kişisel/eğitim amaçlı lisans) — **Yol A (MVP/geliştirme)** için ideal, ama production'da kullanmadan önce BIST'ten ticari lisans alınmalı. Bkz. §6.3 |
| **borsa-api (ibidi)** | CLI/wrapper: endeks, hisse detay, en çok yükselen/düşen, hacim, geçmiş fiyat | Hızlı prototipleme için kullanılabilir |
| **RapidAPI — BIST100 Stock Data** | 15 dk gecikmeli, 30 sn'de bir güncellenen BIST100 anlık verisi | Ücretli/rate-limitli; ölçeklenme öncesi değerlendirilmeli |
| **nosyapi BIST API** | 15 dk gecikmeli veri, kredi bazlı ücretlendirme, öğrenci/kuruluş kontenjanı | Küçük ölçekte başlamak için uygun olabilir |
| **Genel haber siteleri / RSS (Paratic, Hisse.net vb.)** | KAP haberlerini yeniden yayınlayan üçüncü taraf siteler | Yedek/tamamlayıcı kaynak; birincil kaynak KAP olmalı |

**Öneri:** Faz 1 MVP'sinde **borsapy (Yol A)** birincil kaynak olsun — hem bildirim (`Ticker.news`) hem sektör hem fiyat verisi tek kütüphaneden gelir, geliştirme hızlanır. Şirket kuruluşu + Borsa İstanbul sözleşmesi tamamlandığında **KAP REST API'ye (Yol B)** geçilir.

---

## 5. Teknik Stack Önerisi (yeni, flight tracker projesinden bağımsız)

Sub-agent yoğun, zamanlanmış (scheduled) ve çok sayıda paralel işlem içeren bir sistem olduğu için:

- **Orkestrasyon / Agent Katmanı:** LangGraph (durum bazlı, graf tabanlı çoklu-agent orkestrasyonu; checkpointing ve hata kurtarma desteği güçlü — çok sayıda agent'ı yönetirken CrewAI'a göre daha şeffaf/debug edilebilir)
- **Backend / API:** Python + FastAPI (agent'larla doğal entegrasyon, async destek)
- **Zamanlama / İş Kuyruğu:** Celery + Redis (günlük/periyodik tetiklemeler, agent görev kuyruğu)
- **Veritabanı:** PostgreSQL (yapılandırılmış haber/blog verisi, şirket-sektör ilişkileri)
- **Frontend:** Next.js (SEO açısından blog içeriği için kritik, SSR/ISR uygun)
- **LLM Sağlayıcı:** Claude API (yazım, sınıflandırma, özetleme agent'ları için)
- **İçerik Depolama:** PostgreSQL + (ileride) bir headless CMS değerlendirilebilir

> Bu öneri bir başlangıç noktasıdır — birlikte detaylandırıp gerekirse değiştirebiliriz.

---

## 6. Açık Sorular — Cevaplandı

### 6.1 KAP API'ye ücretsiz erişim — ✅ DOĞRULANDI, ÇALIŞIYOR

**MKK API Portal** üzerinden ücretsiz erişim sağlandı ve gerçek veri çekimi test edildi: **https://apiportal.mkk.com.tr/**

**Kurulum adımları (tamamlandı):**
1. apiportal.mkk.com.tr'de hesap açıldı
2. "Borsa Haber Platformu" adında bir **Uygulama (Application)** oluşturuldu → bir **API Key** üretildi (Aktif durumda)
3. KAP Veri Yayın Servisleri ürününe bu uygulama ile **abone olundu** (Ücretsiz plan — **dakikada 6 çağrı limiti / throttling**)
4. Swagger test panelinde ("Dene") gerçek bir istek atılıp **200 OK + gerçek veri** alındı

**Kimlik doğrulama (auth) detayı — ✅ Claude Code implementasyonuyla doğrulandı:**
- Servis, **Base64 Kullanıcı adı/Token** tipi kimlik doğrulama kullanıyor
- Swagger test panelindeki `apikey` header alanı görsel bir kolaylıktı — **gerçek mekanizma Basic Auth**: `Authorization: Basic base64(ClientID:ClientSecret)`. Portaldaki "API Anahtarı" = ClientID, "API Secret" = ClientSecret
- Kod tarafında bu artık `KAP_API_CLIENT_ID` / `KAP_API_CLIENT_SECRET` olarak ayrıştırılmış durumda (eski tek parça `KAP_API_KEY` yapısı kaldırıldı)
- Test ortamında `generateToken`/Bearer akışına gerek yok, direkt Basic Auth yeterli
- ⚠️ **Güvenlik notu:** Credential'lar `.env` dosyasında tutuluyor, repoya commit edilmiyor — ✅ tamamlandı

**Rate limit davranışı — ✅ doğrulandı:** Dakikada 6 istek sınırı aşıldığında API **429 hata kodu, `ERR-224`** dönüyor. Kod tarafında bunu yakalayan özel bir `KAPThrottled` exception'ı tanımlanmış.

**Kapsamdaki 12 servis (KAP Dokümantasyon sekmesinden doğrulandı):**

| Servis | Fonksiyon |
|---|---|
| `generateToken` | Token Alma Servisi |
| `disclosures` | Bildirim Listesi Servisi ✅ test edildi |
| `disclosureDetail` | Bildirim Detay Servisi |
| `downloadAttachment` | Bildirim ek dosyaları servisi |
| `lastDisclosureIndex` | Yayınlanmış Son Bildirim id Servisi ✅ test edildi |
| `members` | Şirket Listesi Servisi |
| `memberDetail` | Şirket Detay Servisi |
| `funds` | Fon Listesi Servisi |
| `fundDetail` | Fon Detay Servisi |
| `memberSecurities` | Şirket Kıymet Bilgileri Servisi |
| `blockedDisclosures` | Erişime Kapatılmış Bildirimler Servisi |
| `caEventStatus` | Hak Kullanım Süreç Durum Servisi |

**`disclosureClass` / `disclosureType` — geçerli değerler (ikisi de aynı kod setini kullanıyor, dikkat: ikisi de aynı kategoriden seçilmeli):**

| Kod | Anlamı |
|---|---|
| `FR` | Finansal Rapor Bildirimi (SPK finansal raporlama: tablo, faaliyet raporu, sorumluluk beyanı, entegre rapor) |
| `ODA` | Özel Durum Açıklaması Bildirimi (SPK özel durum düzenlemeleri kapsamında açıklanan bildirimler) — **en sık/güncel akış bu** |
| `DG` | Diğer Bildirim |
| `DUY` | Düzenleyici Kurum Bildirimi (SPK, Borsa, MKK, Takasbank vb.) |
| `FON` | Fon Bildirimi (sadece `disclosureType` için) |
| `CA` | Hak Kullanım Bildirimi (genel kurul, sermaye artırımı, kar payı — sadece `disclosureType` için) |

**Doğrulanmış çalışma akışı:**
1. `GET /lastDisclosureIndex` → güncel index'i al (auth: `apikey` header) — örnek dönen değer: `1231017`
2. `GET /disclosures?disclosureIndex={index}&disclosureTypes=ODA&disclosureClass=ODA` → o andan itibaren bildirim listesi (title, companyId, subReportIds, disclosureIndex) — **gerçek şirket verisiyle test edildi** (ör. ATP Yazılım, Kuzey Boru, Eminiş Ambalaj)
3. `GET /disclosureDetail/{disclosureIndex}?fileType=html&subReportList={subReportId}` → **tam bildirim içeriği** — ✅ test edildi ve çalışıyor

**`disclosureDetail` — dönen alanlar (gerçek örnekle doğrulandı):**

| Alan | İçerik |
|---|---|
| `senderTitle` / `senderId` | Bildirimi gönderen şirket adı/ID'si |
| `disclosureReason` | Bildirim sebebi (ör. `NEW`) |
| `subject.tr` / `subject.en` | Bildirim başlığı (TR/EN) |
| `summary.tr` / `summary.en` | **Kısa özet — blog başlığı/girişi için doğrudan kullanılabilir malzeme** |
| `time` | Bildirim zamanı |
| `link` | Orijinal KAP sayfası linki (kaynak göstermek için) |
| `htmlMessages` | İçinde `id` (subReportId) ve **Base64 kodlanmış tam HTML bildirim metni** (`tr`/`en`) — decode edilince tüm detaylar (tutarlar, tarihler, açıklamalar) çıkıyor |

⚠️ **Teknik not:** `htmlMessages` içeriği Base64 + HTML formatında geliyor. Sub-agent akışında bir **"Decode & Parse" adımı** gerekecek: Base64 çöz → HTML'den düz metni çıkar (ör. BeautifulSoup/benzeri bir HTML parser ile) → LLM'e temiz metin olarak ver. Bu adım "Analiz/Özetleyici Agent"ın (bkz. §3) ilk işi olacak.

**disclosureDetail parametreleri:**

| Parametre | Tip | Açıklama |
|---|---|---|
| `disclosureIndex` | PATH | Bildirimin index'i |
| `fileType` | QUERY | `html` (varsayılan) |
| `subReportList` | QUERY | `/disclosures`'tan gelen `subReportIds` değeri |
| `apikey` (görsel) → gerçekte Basic Auth | HEADER | `Authorization: Basic base64(ClientID:Secret)` — Auth için gerekli |

**Önemli mimari not:** Ücretsiz plan **dakikada 6 çağrı** ile sınırlı. Bu, sub-agent kuyruk tasarımını doğrudan etkiliyor — "Kaynak Tarayıcı Agent" bu limite uygun bir rate-limiter/backoff mekanizmasıyla çalışmalı, aksi halde 429/throttling hatası alınır. Min. 100 yazı/gün hedefiyle birlikte düşünüldüğünde, bu limit erken aşamada yeterli olsa da ölçeklenme sırasında ücretli plana geçiş ihtiyacı değerlendirilmeli.

### 6.1.1 members servisi — test edildi

**URL:** `/api/vyk/members` | **Method:** GET | **Parametre yok**

⚠️ **Production auth farkı:** Servis dokümantasyonunda önemli bir not var — *"Header bilgisinde yer alan Authorization alanında generateToken servisinden alınan token bilgisi yer alır. (Canlı ortam için geçerli olup, test ortamı için token alma işlemi söz konusu değildir.)"* Yani **test ortamında** (`apigwdev`) bizim kullandığımız basit `apikey` header'ı yeterliyken, **production ortamına geçildiğinde** önce `generateToken` servisinden bir token alıp bunu `Authorization` header'ına koymak gerekecek — bu, canlıya alma öncesi ayrı bir entegrasyon adımı.

**Dönen alanlar:**

| Alan | Tip | Açıklama |
|---|---|---|
| `Id` | Integer | Şirketin uniq ID'si (companyId ile eşleşiyor) |
| `Title` | String | Şirket unvanı |
| `stockCode` | String | Hisse kodu/kodları (birden fazla olabilir) |
| `memberType` | String | Kurum tipi: IGS (İşlem Gören Şirket), IGMS (İşlem Görmeyen Şirket), YK (Yatırım Kuruluşu), PYS (Portföy Yönetim Şirketi), DDK, FK, BDK, DCS, DS, DG |
| `kfifUrl` | String | Katılım Finans İlkeleri Bilgi Formu linki (opsiyonel) |

❗ **Önemli bulgu — sektör bilgisi YOK:** `members` servisi sektör/endüstri bilgisi döndürmüyor, sadece kurum tipi (`memberType`) veriyor — bu bir şirketin "banka mı, yatırım kuruluşu mu" olduğunu söylüyor, "bankacılık sektöründe mi, enerji sektöründe mi" olduğunu söylemiyor. **Sonuç:** Sektör sınıflandırması için KAP tek başına yeterli değil; §6.3'te planlanan BIST sektör endeksleri (XBANK, XGIDA vb.) verisi **ayrı bir kaynaktan** (borsapy/borsa-api) çekilip `stockCode` üzerinden KAP verisiyle eşleştirilmeli.

**Gerçek örnek yanıt (doğrulandı):**
```json
[
  {
    "id": "5900",
    "title": "1000 YATIRIMLAR HOLDİNG A.Ş.",
    "stockCode": "BINHO",
    "memberType": "IGS",
    "kfifUrl": "https://www.kap.org.tr/tr/kfif/8acae2c48b2fa25a018bba0a5034596d"
  },
  {
    "id": "2501",
    "title": "24 GAYRİMENKUL VE GİRİŞİM SERMAYESİ PORTFÖY YÖNETİMİ A.Ş.",
    "stockCode": "YGP",
    "memberType": "FK, PYS"
  }
]
```
Not: `memberType` birden fazla değer içerebiliyor (ör. `"FK, PYS"` — hem Fon Kurucu hem Portföy Yönetim Şirketi), parser bunu virgülle ayırıp dizi olarak işlemeli. `kfifUrl` her şirkette olmuyor (opsiyonel alan).

### 6.1.3 Kod Tarafı Durumu — Claude Code ile İlerleme Kaydedildi

Bu proje, ayrıca **Claude Code** ile kodlanmaya başlanmış durumda (`app/`, `alembic/`, `tests/` içeren bir FastAPI projesi). Mevcut dosya yapısı:

| Dosya | Durum |
|---|---|
| `app/config.py` | KAP ayarları: `KAP_API_CLIENT_ID`/`_SECRET`, `_BASE_URL`, `_PREFIX`, `_USE_TOKEN`, `_TOKEN_URL` |
| `app/scrapers/kap_api_client.py` | `KAPApiClient` sınıfı — Basic+Bearer auth, throttle exception, base64 decoder |
| `app/scrapers/__init__.py` | `KAPApiClient` export edilmiş |
| `.env` / `.env.example` | Yeni şemaya göre temizlenmiş, çalışan credential'lar `.env`'de |
| `_kap_api_smoke.py` | Duman testi — geçiyor ✅ |

### 6.1.4 Production Erişimi — MKK'dan Resmi Cevap Geldi (Kesinleşti)

MKK'nın **kapdestek@mkk.com.tr** üzerinden verdiği resmi cevap, production sürecini tamamen netleştirdi:

🚨 **KRİTİK BULGU — Kurumsal kimlik zorunlu:** *"Canlı ortam erişimi için kurumsal bir kimliğe sahip olunması gerekmektedir. **Bireysel abonelik bulunmamaktadır.**"* Bu, projenin gerçek kullanıcılara açılabilmesi için **önce bir şirket (ör. limited şirket) kurulması gerektiği** anlamına geliyor — bireysel/öğrenci olarak şu anki haliyle production erişimi mümkün değil. Bu, projenin genel iş planında (00-genel-bakis.md) ayrıca ele alınması gereken bir ön koşul.

| Konu | Kesinleşen Cevap |
|---|---|
| **Sözleşme gerekliliği** | Evet — Borsa İstanbul ile **"Veri Yayın Sözleşmesi"** imzalanmadan canlı ortama geçilemiyor. Başvuru: **vyk-marketing@borsaistanbul.com** |
| **Kurumsal kimlik** | Zorunlu — bireysel abonelik yok |
| **Production host adresi** | Sözleşme tamamlandıktan sonra ayrıca iletiliyor (şu an bilinmiyor, bilinemez de) |
| **Auth akışı (generateToken)** | Doğrulandı: API Key → `generateToken` → dönen token `Authorization` header'ında kullanılıyor. **Test ortamında bu adıma gerek yok** (Claude Code'daki `_USE_TOKEN` bayrağı bu yüzden test'te false, production'da true olmalı) |
| **IP whitelisting** | Production'da **statik IP bazlı yetkilendirme** var — sözleşme sonrası kullanılacak sunucu IP'lerinin MKK'ya bildirilmesi gerekiyor |
| **Rate limit (production)** | **Dakikada 1.000 çağrı** — test ortamındaki (dk 6) limitten **166 kat daha yüksek**. Min. 100 yazı/gün hedefi için bu limit fazlasıyla yeterli, ücretli plan diye ayrı bir şey yok, limit sözleşmeyle birlikte geliyor |
| **İçerik yeniden yayın lisansı** | KAP verisinin bir web sitesi/uygulama/haber platformunda **son kullanıcılara sunulması, yeniden dağıtılması ayrıca Veri Yayın Sözleşmesi kapsamında** değerlendiriliyor — yani sadece "veriye erişim" değil, "bu veriyi başkalarına gösterme" hakkı da bu sözleşmenin konusu |

**Sonuç:** Rate limit için "ücretli plan var mı" sorusu artık anlamsız — sınır, ücretli bir plandan değil, doğrudan sözleşme ile birlikte geliyor (dk 1.000). Bu maddeyi kapatıyoruz.

### 6.1.5 Kalan İşler (Faz 1 için)
- [x] ~~API Key'in `.env` dosyasına taşınması ve asla repoya commit edilmemesi~~ ✅ **TAMAMLANDI**
- [x] ~~Rate limit (dk 6 çağrı) için ücretli plan seçeneklerinin araştırılması~~ ✅ **CEVAPLANDI** — ücretli plan yok, production'da otomatik dk 1.000 limit (sözleşmeyle birlikte)
- [x] ~~Sektör verisi kaynağı~~ ✅ **ÇÖZÜLDÜ** — borsapy (Yol A) hem sektör hem bildirim veriyor, MVP için ek kaynağa gerek yok
- [x] ~~Yol A entegrasyonu~~ ✅ **KODLANDI VE TEST EDİLDİ** — `app/scrapers/` altında `disclosure_source.py` (ortak arayüz), `borsapy_source.py` (Yol A), `kap_api_source.py` (Yol B adapter — şablon, KAPApiClient metod isimleriyle eşleştirilmeli), `source_factory.py` (`.env`'deki `DATA_SOURCE` değişkenine göre kaynak seçimi)
- [ ] **Şirket kurulumu** (kurumsal kimlik) — Yol B (production) erişiminin ön koşulu, proje genelinde ayrı bir iş kalemi olarak planlanmalı
- [ ] Borsa İstanbul ile **Veri Yayın Sözleşmesi** başvurusu (vyk-marketing@borsaistanbul.com) — şirket kurulduktan sonra atılacak adım, borsapy ticari lisansı da aynı görüşmede sorulabilir
- [ ] Sözleşme sonrası: production host adresi, statik IP tanımlama, `generateToken` akışının gerçek ortamda test edilmesi
- [ ] `memberDetail` servisinin sektör bilgisi içerip içermediğinin kontrolü (düşük öncelik artık — borsapy zaten sektör veriyor)

### 6.2 Dil (Türkçe / İngilizce)
Kullanıcının IP adresine göre otomatik dil tespiti yapılacak — yurt dışından bağlanan kullanıcıya içerik İngilizce, Türkiye'den bağlanana Türkçe gösterilecek.
- Bu, sub-agent içerik üretim akışına bir **çeviri/lokalizasyon agent'ı** eklenmesi gerektiği anlamına geliyor (her blog yazısı iki dilde üretilecek ya da orijinali üretilip otomatik çevrilecek — karar verilmeli)
- Teknik not: IP bazlı yönlendirme için Next.js middleware + bir GeoIP servisi (ör. Cloudflare'in ülke header'ı, ya da bir GeoIP API'si) kullanılabilir

### 6.3 Sektör sınıflandırması — Araştırıldı, Genişletildi

BIST'in kendi resmi sektör sınıflandırması kullanılacak. **borsapy** kütüphanesi bu veriyi ve fazlasını doğrudan sağlıyor:

- `bp.sectors()` → **53 sektörün tam listesi** (Bankacılık, Holding ve Yatırım, Enerji, Gıda, vb.)
- `bp.Ticker("THYAO").info["sector"]` / `info["industry"]` → hisse bazlı sektör ve alt sektör bilgisi
- `bp.screen_stocks(sector="Bankacılık", ...)` → sektöre göre hisse filtreleme, **40+ kriter** (F/K, ROE, temettü verimi, piyasa değeri vb.) — bu, Faz 2'nin screener özelliği için doğrudan hazır bir temel
- `bp.stock_indices()` → BIST 30/50/100/BANKA gibi endeks listesi
- `bp.Index("XBANK").components` → sektör endekslerinin bileşen listesi (XBANK, XGIDA, XUSIN, XUTEK vb. — Borsa İstanbul'un resmi sektör endeksleri)
- **Yeni bulgu:** `bp.Ticker(symbol).news` / `.calendar` / `.earnings_dates` → **KAP bildirimlerini doğrudan sağlıyor**, ayrı bir KAP entegrasyonuna gerek kalmadan MVP'yi çalıştırmayı mümkün kılıyor (bkz. §2, Yol A)
- **Bonus:** `bp.EVDS()` → TCMB'nin ücretsiz makro veri API'si (145 kategori — enflasyon, faiz, döviz, ödemeler dengesi vb.), ileride "piyasa bağlamı" içeriği için kullanılabilir

🚨 **KRİTİK LİSANS UYARISI:** borsapy'nin resmi dokümantasyonunda açıkça şu uyarı var:
> *"Bu kütüphane yalnızca kişisel kullanım ve eğitim amaçlıdır. **Ticari yazılım ürünleri geliştirmek, ticari hizmetlerde kullanmak veya herhangi bir ticari amaçla kullanılamaz.** Ticari kullanım için uygun bir lisans satın almak üzere Borsa İstanbul ile iletişime geçmelisiniz."*

Bu bulgu nedeniyle **Faz 4 (Abonelik) şimdilik yol haritasından çıkarıldı** (bkz. `00-genel-bakis.md`) — platform önce ücretsiz/kişisel proje aşamasında (**Yol A**) geliştirilecek. Ama şu netçe not düşülmeli: platform gerçek kullanıcılara açılıp **halka açık bir servis** haline geldiğinde (abonelik olmasa bile) hem borsapy'nin lisans şartları hem KAP'ın Veri Yayın Sözleşmesi (§6.1.4) gerekecek — ikisi de aynı temel kısıtın (BIST/MKK verisinin ticari/kamuya açık kullanımı) farklı yüzleri. İki uzun vadeli seçenek var:
1. **Borsa İstanbul ile iletişime geçip ticari lisans satın almak** (borsapy'nin kendi önerdiği yol) — muhtemelen KAP Veri Yayın Sözleşmesi ile aynı süreç/görüşme kapsamında birlikte çözülebilir
2. Sektör/endeks eşleştirme verisini **kendi kaynağımızdan** oluşturmak (uzun vadede daha bağımsız ama daha maliyetli)

**Durum:** Şimdilik borsapy ile devam ediyoruz (Yol A, kişisel/eğitim aşaması). Platform gerçek kullanıcı trafiği almaya başladığında bu konu, KAP production geçişiyle (§6.1.4) birlikte tek bir "ticarileşme" görüşmesinde ele alınabilir.

### 6.4 Günlük yayın hacmi
Sabit değil, **güne göre değişecek** — o gün kaç önemli KAP bildirimi/haber varsa ona göre üretim yapılacak. **Minimum hedef: günde ~100 yazı.**
- Bu, sub-agent sisteminin yüksek paralellik ve verimli kuyruk yönetimi (Celery/Redis) gerektirdiğini doğruluyor
- Ölçek notu: günde 100+ yazı, LLM API maliyeti açısından önceden bütçelenmeli (Claude API kullanım maliyeti Faz 1 planlamasında hesaba katılmalı)

### 6.5 İçerik kalite kontrolü
**Tamamen otomatik** olacak — manuel editör onayı yok.
- Bu karar, "Editör/Kalite Kontrol Agent" rolünün (bkz. §3) sistemdeki en kritik bileşenlerden biri haline geldiği anlamına geliyor; yanlış/yanıltıcı finansal bilgi riskine karşı bu agent'ın güçlü doğrulama kuralları (ör. sayısal verilerin kaynak bildirimle çapraz kontrolü, halüsinasyon tespiti) içermesi önemli
- Yasal/itibar riski açısından not: otomatik yayınlanan finansal içerikte hata payını azaltmak için Editör Agent'a "kaynağa sadık kal, spekülasyon yapma" tarzı katı kısıtlar konulmalı

---

## 7. Faz 1 Durum Özeti

| Bileşen | Durum |
|---|---|
| KAP veri erişimi — Yol B (resmi API) | ✅ Doğrulandı, test ortamında çalışıyor; Claude Code'da `KAPApiClient` olarak kodlandı |
| Bildirim + sektör verisi — Yol A (borsapy, MVP) | ✅ Kodlandı ve test edildi (`BorsapySource`, `source_factory`) — gerçek ağ testi sadece bilgisayarında yapılabilir |
| Şirket listesi (members, Yol B) | ✅ Test edildi — sektör bilgisi içermiyor (önemi azaldı, borsapy sektörü zaten veriyor) |
| Sektör sınıflandırma kaynağı | ✅ borsapy ile çözüldü — hem sektör hem bildirim hem tarama (screener) tek kütüphaneden |
| Sub-agent mimarisi (roller, akış, Yol A/B soyutlaması) | ✅ Tanımlandı |
| Teknik stack | ✅ Önerildi (LangGraph + FastAPI + Celery/Redis + PostgreSQL + Next.js + Claude API) — FastAPI iskeleti Claude Code ile kurulmaya başlandı |
| Dil/lokalizasyon yaklaşımı | ✅ Karar verildi (IP bazlı yönlendirme + çeviri agent'ı) |
| Günlük hacim hedefi | ✅ Belirlendi (min. ~100 yazı/gün, değişken) |
| Kalite kontrol yaklaşımı | ✅ Belirlendi (tamamen otomatik) |
| API Key güvenliği (.env) | ✅ **TAMAMLANDI** — `.env`'de, Basic Auth (ClientID/Secret) olarak yapılandırıldı |
| Rate limit davranışı (test, Yol B) | ✅ Doğrulandı (429 ERR-224, `KAPThrottled` exception ile yakalanıyor) |
| Production auth akışı (generateToken/Bearer, Yol B) | ✅ Süreç netleşti, MKK resmi cevabıyla doğrulandı — sözleşme tamamlanmadan gerçek ortamda test edilemez |
| Production rate limit (Yol B) | ✅ Netleşti — **dakikada 1.000 çağrı** (sözleşmeyle birlikte geliyor) |
| **Kurumsal kimlik (şirket kuruluşu)** | ⏳ Açık — Yol B'ye (gerçek kullanıcı erişimi) geçişin ön koşulu |
| **Veri Yayın Sözleşmesi (Borsa İstanbul)** | ⏳ Açık — şirket kurulduktan sonra vyk-marketing@borsaistanbul.com üzerinden başvurulacak |
| `memberDetail` sektör kontrolü | ⏳ Düşük öncelik — borsapy zaten sektör veriyor, gerek kalmayabilir |

**Sonuç:** Faz 1'in *teknik tanım* aşaması tamamlandı ve **MVP'yi hemen başlatacak bir yol (Yol A, borsapy) hem tanımlandı hem kodlandı**. Kod tarafında sıradaki somut adım: `kap_api_source.py` şablonundaki `TODO`'ları gerçek `KAPApiClient` metod isimleriyle doldurmak (düşük öncelik, Yol B zaten çalışıyor sadece adapter'ı eksik) ve sub-agent zincirinin geri kalanını (Analiz/Yazar/Editör/Yayıncı agent'ları) `get_disclosure_source()` üzerine inşa etmek. Kurumsal/hukuki taraf (şirket + Borsa İstanbul sözleşmesi) ayrı, paralel giden bir iş kalemi olarak kalıyor — gerçek kullanıcılara açılmadan önce tamamlanması gerekiyor.
