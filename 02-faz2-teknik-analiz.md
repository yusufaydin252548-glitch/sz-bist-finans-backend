# Faz 2: İnteraktif Teknik Analiz Modülü

**Öncelik:** 2. sıra (Faz 1'den sonra)

---

## 1. Ne yapacak?
- Kullanıcıların BIST hisseleri üzerinde grafik/indikatör bazlı teknik analiz yapabildiği interaktif araçlar
- Farklı "teknik analiz modları": tekil gösterge sorgulama, tam seri grafik, TradingView tarzı AL/SAT/TUT sinyal özeti, hisse tarama (screener)

---

## 2. Veri Kaynağı — borsapy (Yol A ile aynı kütüphane, Faz 1 §2)

Faz 1'de zaten borsapy'yi bildirim/sektör kaynağı olarak seçtik (Yol A). Faz 2, **aynı kütüphaneyi** teknik analiz için kullanır — ayrı bir entegrasyon gerekmiyor, tek bağımlılık yeterli.

⚠️ Aynı lisans notu geçerli: kişisel/eğitim amaçlı kullanım, gerçek kullanıcılara açılmadan önce ticari lisans/sözleşme gerekiyor (bkz. Faz 1 §6.1.4, §6.3).

### 2.1 Tekil Göstergeler
```python
hisse = bp.Ticker("THYAO")
hisse.rsi(); hisse.macd(); hisse.bollinger_bands()
hisse.atr(); hisse.stochastic(); hisse.adx(); hisse.supertrend()
```
14 farklı gösterge tek satırla çekilebiliyor (RSI, MACD, Bollinger, ATR, Stochastic, ADX, OBV, VWAP, Supertrend, Tilson T3, HHV, LLV, MOM, ROC, WMA, DEMA, TEMA).

### 2.2 Tam Seri (Grafik için)
```python
df = hisse.history_with_indicators(period="3ay")
# OHLCV + tüm göstergeler tek DataFrame'de — grafik kütüphanesine doğrudan verilebilir
```

### 2.3 TradingView Tarzı AL/SAT/TUT Sinyalleri
```python
signals = hisse.ta_signals()
signals['summary']['recommendation']  # STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
signals['oscillators'], signals['moving_averages']  # detaylı kırılım
```
Bu, "teknik analiz modları" fikrinin en somut karşılığı — kullanıcıya tek bakışta özet verebilir, farklı zaman dilimlerinde (`interval="1h"`, `"1d"`, `"1W"`) çalışıyor.

### 2.4 Hisse Tarama (Screener)
```python
bp.screen_stocks(template="high_dividend")     # hazır şablonlar
bp.screen_stocks(pe_max=10, dividend_yield_min=3, sector="Bankacılık")  # özel filtre
bp.scan("XU030", "rsi < 30 and volume > 1000000")  # teknik gösterge bazlı tarama
```
40+ temel kriter (F/K, ROE, temettü verimi, piyasa değeri) + teknik koşul bazlı tarama (`crosses_above`, `rsi < 30` vb.) hazır geliyor — kullanıcıya "bugün RSI'ı 30 altına düşen hisseler" gibi interaktif sorgular sunulabilir.

### 2.5 Gerçek Zamanlı Akış (opsiyonel, ileri aşama)
```python
stream = bp.TradingViewStream()
stream.subscribe("THYAO")
quote = stream.get_quote("THYAO")  # <1ms, cache'den
```
Varsayılan olarak **~15 dakika gecikmeli**. Gerçek zamanlı için TradingView Pro hesabı + BIST Real-time Market Data paketi (ek ücretli, ayrı bir TradingView aboneliği) gerekiyor.

### 2.6 Alternatif Kaynaklar (yedek/karşılaştırma)
- **borsa-api (ibidi)** — geçmiş fiyat verisi, endeks/hisse detay
- **RapidAPI BIST100 Stock Data / nosyapi** — 15 dk gecikmeli veri, ücretli/kredi bazlı

---

## 3. Açık Sorular — İlk Değerlendirme

### 3.1 Hangi teknik analiz modları desteklenecek?
**Öneri:** MVP'de 3 mod yeterli olur:
1. **Genel Bakış** — `ta_signals()` özeti (AL/SAT/TUT + kaç gösterge hangi yönde)
2. **Grafik + Gösterge** — `history_with_indicators()` ile mum grafiği üzerine RSI/MACD/Bollinger seçilebilir katmanlar
3. **Tarama (Screener)** — hazır şablonlar (`high_dividend`, `low_pe`, `high_roe`) + özel filtre kurucu

### 3.2 Gerçek zamanlı mı, gecikmeli mi?
**Öneri:** MVP'de **15 dakika gecikmeli** (varsayılan, ek maliyet yok) ile başla. Gerçek zamanlı veri hem TradingView Pro aboneliği hem BIST Real-time paketi gerektiriyor — bu, kullanıcı talebi netleşmeden erken bir maliyet. İleride premium bir özellik olarak değerlendirilebilir (not: Faz 4 abonelik şu an planlama dışı, bkz. `00-genel-bakis.md`).

### 3.3 Grafik kütüphanesi seçimi
**Öneri:** Next.js frontend'de **TradingView Lightweight Charts** (ücretsiz, açık kaynak, hafif) — `history_with_indicators()` çıktısı bu kütüphanenin beklediği formata kolayca dönüştürülebilir. TradingView'ın ücretli widget'larına gerek yok.

### 3.4 Kullanıcı bazlı özelleştirme (izleme listesi, alarm)
Henüz karar verilmedi — kullanıcı hesap sistemi Faz 3 (Community) ile birlikte düşünülmeli, çünkü ikisi de "kullanıcı profili" kavramına dayanıyor. Faz 3 planlanırken bu soru birlikte ele alınmalı.

---

## 4. Faz 2 için Sonraki Somut Adım
Faz 1'in `BorsapySource` sınıfı zaten kodlandı (bkz. Faz 1 §2, Yol A). Faz 2 için benzer şekilde bir `TechnicalAnalysisService` sınıfı yazılabilir — `ta_signals()`, `history_with_indicators()` ve `screen_stocks()` çağrılarını sarmalayıp FastAPI endpoint'lerine bağlayan ince bir katman. Bu, Faz 1 tamamlanıp sub-agent içerik motoru çalışır hale geldikten sonra ele alınacak.
