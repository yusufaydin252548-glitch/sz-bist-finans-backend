# Faz 3: Community / Sosyal Katman

**Öncelik:** 3. sıra (Faz 1 ve Faz 2'den sonra)

---

## 1. Ne yapacak?
- Gerçek kullanıcıların ve gerçek ekonomistlerin yazı paylaşabildiği bir alan
- Küçük ölçekli sosyal medya mantığı — takip, yorum, beğeni gibi etkileşim özellikleri (kapsamı netleştirilecek)
- Sub-agent üretimi içerik ile gerçek kullanıcı/ekonomist içeriğinin bir arada, ayrıştırılabilir şekilde sunulması

## 2. Açık Sorular — Cevaplandı

### 2.1 Kullanıcı içerik üretimi nasıl olacak? — ✅ KARARLAŞTIRILDI
Tamamen serbest paylaşım. Genel kullanıcı da, "ekonomist" etiketini kullanmak isteyen kullanıcı da ayrı bir başvuru/onay/kimlik doğrulama sürecinden geçmeyecek — **kullanıcı beyanı yeterli**. "Ekonomist" bir profil etiketi olarak kullanıcının kendi seçimiyle işaretlenir, admin onaylı bir statü değildir.

### 2.2 Moderasyon stratejisi ne olacak? — ✅ KARARLAŞTIRILDI
**Tamamen otomatik.** Faz 1'deki sub-agent içerik kalite kontrolüyle tutarlı bir yaklaşım (bkz. Faz 1 §6.5) — manuel inceleme kuyruğu veya insan onayı yok.

### 2.3 Sosyal özellikler kapsamı — MVP'de hangileri olacak? — ✅ KARARLAŞTIRILDI
MVP: **takip + yorum + beğeni**. **Direkt mesaj (DM) MVP dışında** — moderasyon yükünü ve kötüye kullanım yüzeyini artırıyor, çekirdek değer (içerik) için gerekli değil. İleride ayrı bir karar olarak değerlendirilebilir.

### 2.4 İtibar/rozet sistemi olacak mı? — ✅ KARARLAŞTIRILDI
Sadece **"Ekonomist"** profil rozeti olacak (§2.1'deki gibi kullanıcı beyanına dayalı, doğrulama süreci yok). Puan/seviye tabanlı geniş bir itibar sistemi MVP kapsamında yok.

### 2.5 Sub-agent içerikleri ile kullanıcı içerikleri akışta nasıl ayrıştırılacak? — ✅ KARARLAŞTIRILDI
Veri modelinde bir `content_type` alanı (`sub_agent` / `user` / `economist`) tutulur; akışta her kart bu tipe göre görsel olarak etiketlenir (ör. rozet/renk/ikon: "Otomatik Analiz" vs "Topluluk" vs "Ekonomist"). Kullanıcı bu tipe göre filtreleyebilir — hangi içeriğin otomatik üretildiği, hangisinin gerçek bir kişiden geldiği her zaman ayırt edilebilir olmalı (şeffaflık).

⚠️ **Not:** §2.1/§2.4'te "ekonomist" etiketinin kullanıcı beyanına dayalı olması, gerçek bir doğrulama içermediği anlamına geliyor — yanlış/yanıltıcı unvan beyanı riski var. Bu, moderasyon tamamen otomatik olduğu için (§2.2) manuel bir kontrol noktasıyla da yakalanmayacak. İleride bu risk büyürse (ör. sahte "ekonomist" hesapların yanıltıcı içerik yayması) etiketleme politikası gözden geçirilebilir.

---

> Bu dosya Faz 1 ve Faz 2 netleştikten sonra daha detaylı bir mimari ile genişletilecek.
