# Faz 2: İnteraktif Teknik Analiz Modülü

**Öncelik:** 2. sıra (Faz 1'den sonra)

---

## 1. Ne yapacak?
- Kullanıcıların BIST hisseleri üzerinde grafik/indikatör bazlı teknik analiz yapabildiği interaktif araçlar
- Farklı "teknik analiz modları": tekil gösterge sorgulama, tam seri grafik, Trend/Swing Gösterge Özeti, hisse tarama (screener)
- 15 dakika gecikmeli veriye uygun, yanıltıcı olmayan "Günlük/Haftalık Trend ve Salınım (Swing)" analiz odağı

---

## 2. Veri Kaynağı & Mimari — borsapy + Redis Cache

Faz 1'de zaten borsapy'yi bildirim/sektör kaynağı olarak seçtik (Yol A). Faz 2, **aynı kütüphaneyi** teknik analiz için kullanır — ayrı bir entegrasyon gerekmiyor, tek bağımlılık yeterli.

### 2.1 Performans & Rate Limit Koruması: Redis Önbellek (Caching) Katmanı
Teknik analiz hesaplamaları (`history_with_indicators`, `ta_signals` vb.) CPU ve ağ açısından maliyetlidir. Yüzlerce kullanıcı aynı anda popüler hisseleri (THYAO, EREGL vb.) sorguladığında backend'in kilitlenmesini ve IP ban riskini engellemek için **Redis Caching** katmanı zorunludur:

- **Grafik Serileri (`history_with_indicators`):** TTL: **15 dakika** (`cache_key = ta:history:{symbol}:{period}:{interval}`)
- **Trend/Sinyal Özetleri (`ta_signals`):** TTL: **15 dakika** (`cache_key = ta:signals:{symbol}:{interval}`)
- **Hazır Tarama (Screener) Sonuçları:** TTL: **30 dakika** (`cache_key = ta:screener:{template}`)
- *Sonuç:* Kullanıcı istekleri doğrudan bellekten (Redis) 2-5 milisaniyede yanıtlanır, `borsapy` sadece önbellek süresi dolduğunda arka planda tetiklenir.

### 2.2 Tekil Göstergeler
```python
hisse = bp.Ticker("THYAO")
hisse.rsi(); hisse.macd(); hisse.bollinger_bands()
hisse.atr(); hisse.stochastic(); hisse.adx(); hisse.supertrend()
```
14 farklı gösterge tek satırla çekilebiliyor (RSI, MACD, Bollinger, ATR, Stochastic, ADX, OBV, VWAP, Supertrend, Tilson T3, HHV, LLV, MOM, ROC, WMA, DEMA, TEMA).

### 2.3 Trend & Salınım (Swing) Gösterge Özeti (15 Dk Gecikmeye Uygun)
```python
signals = hisse.ta_signals(interval="1d") # Günlük bazda trend analizi
signals['summary']['recommendation']  # STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
signals['oscillators'], signals['moving_averages']  # detaylı kırılım
```
> ⚠️ **Ürün & İletişim Notu:** Veri 15 dakika gecikmeli olduğu için anlık (1dk / 5dk) "Al/Sat Sinyali" algısı oluşturulmaz. Bu özellik arayüzde **"Günlük/4 Saatlik Trend Özeti"** ve **"Teknik Gösterge Dengesi"** olarak sunulur. Böylece kullanıcının gecikmeli veriyle anlık işlem yapıp mağdur olması engellenir.

### 2.4 Tam Seri (Grafik için)
```python
df = hisse.history_with_indicators(period="3ay")
# OHLCV + tüm göstergeler tek DataFrame'de — grafik kütüphanesine doğrudan verilebilir
```

### 2.5 Hisse Tarama (Screener)
```python
bp.screen_stocks(template="high_dividend")     # hazır şablonlar
bp.screen_stocks(pe_max=10, dividend_yield_min=3, sector="Bankacılık")  # özel filtre
bp.scan("XU030", "rsi < 30 and volume > 1000000")  # teknik gösterge bazlı tarama
```
40+ temel kriter (F/K, ROE, temettü verimi, piyasa değeri) + teknik koşul bazlı tarama (`crosses_above`, `rsi < 30` vb.) hazır gelir.

---

## 3. Açık Sorular — Kararlaştırıldı

### 3.1 Hangi teknik analiz modları desteklenecek? — ✅ KARARLAŞTIRILDI
MVP'de 3 mod ile başlanacak:
1. **Trend & Gösterge Dengesi** — Günlük ve 4 saatlik periyotta indikatör dağılımı (Pozitif / Nötr / Negatif gösterge sayısı)
2. **Grafik + Gösterge Katmanları** — `history_with_indicators()` ile mum grafiği üzerine RSI/MACD/Bollinger katmanları
3. **Akıllı Tarama (Screener)** — hazır şablonlar (`high_dividend`, `low_pe`, `high_roe`) + teknik filtreler (aşırı satımdaki hisseler vb.)

### 3.2 Gerçek zamanlı mı, gecikmeli mi? — ✅ KARARLAŞTIRILDI
MVP'de **15 dakika gecikmeli** (ek maliyetsiz) ile başlanacak. Kullanıcıya açıkça *"Veriler 15 dk gecikmelidir — orta ve uzun vadeli trend analizi için uygundur"* bilgilendirmesi yapılacak.

### 3.3 Grafik kütüphanesi seçimi — ✅ KARARLAŞTIRILDI
Next.js frontend'de **TradingView Lightweight Charts** (açık kaynak, hafif, performanslı) kullanılacak.

### 3.4 Kullanıcı bazlı özelleştirme (izleme listesi, alarm) — ⏳ AÇIK
Kullanıcı hesap sistemi Faz 3 (Community) ile birlikte düşünülmeli.

---

## 4. Faz 2 için Sonraki Somut Adım
Faz 1'in ardından `TechnicalAnalysisService` sınıfı yazılacak:
1. `borsapy` çağrılarını sarmalayıp FastAPI endpoint'lerine bağlayacak.
2. Endpoint'lerin önüne **FastAPI-Cache / Redis Decorator** entegre edilecek (15 dk TTL).
3. Sinyal/Trend endpoint'leri `1d` ve `4h` periyotlarına kilitlenerek güvenli trend özetleri döndürecek.

