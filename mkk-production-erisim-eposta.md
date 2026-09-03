Kime: kapdestek@mkk.com.tr
Konu: KAP Veri Yayın Servisleri API - Canlı (Production) Ortama Geçiş Süreci Hk.

Sayın Yetkili,

MKK API Portalı üzerinden kayıtlıyız ve "Borsa Haber Platformu" adlı
uygulamamız ile KAP Veri Yayın Servisleri API ürününe (Ücretsiz plan,
6 çağrı/dk) abone olduk. Test ortamında disclosures, disclosureDetail,
lastDisclosureIndex ve members servislerini başarıyla test ettik.

Canlı ortama geçiş süreci portal dokümantasyonunda net olmadığı için
aşağıdaki konularda bilgi rica ederiz:

1. Canlı (production) ortama geçiş için ayrı bir sözleşme / taahhütname
   imzalanması gerekiyor mu? Gerekiyorsa süreç ve talep edilen evraklar
   nelerdir?

2. Canlı ortam API Gateway host adresi nedir? OpenAPI şemasında yalnızca
   test/dev adresi yer alıyor.

3. generateToken servisinin canlı ortamdaki base URL'i ve kimlik doğrulama
   akışı (ör. client credentials ile token üretimi) nasıl işliyor?
   Dokümantasyonda "test ortamı için token alma söz konusu değildir"
   ifadesi geçiyor, canlı akış için netleştirmenizi rica ederiz.

4. Canlı ortam erişimi için sunucu statik IP adresimizin güvenlik
   duvarınıza (whitelist) tanımlanması gerekiyor mu?
   Sunucu statik IP adresi ilerleyen aşamada temin edilip tarafınıza
   iletilecektir.

5. Ücretsiz planın kota sınırı (6 çağrı/dk) canlı ortamda da geçerli mi?
   Daha yüksek kotalı planlar ve ücretlendirme koşulları mevcut mu?

6. KAP verilerinin bir haber/analiz platformunda yayınlanması açısından
   lisans, atıf veya kullanım kısıtı bulunuyor mu?

Portalda Kayıtlı E-posta: yusufaydin252548@gmail.com
Uygulama Adı: Borsa Haber Platformu
Firma / Geliştirici: Yusuf Aydın (şahıs)
İletişim: +90 552 208 76 64 / yusufaydin252548@gmail.com

Saygılarımızla,
Yusuf Aydın
