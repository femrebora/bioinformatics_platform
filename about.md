# Bioinformatics Platform — Project Overview

## Vizyon

Server-side biyoinformatik pipeline platformu. Kullanıcılar görsel bir arayüzde pipeline modüllerini birbirine bağlar, iş sunucuya gönderilir, compute maliyeti hesaplanır, sonuç döner. Uzun vadede Galaxy benzeri genel bir platform hedefleniyor; ilk domain HLA/immunogenomics.

## Mimari (Hedef)

```
[Browser UI] → [Orchestrator API] → [Cost Estimator] → [EC2 Spawner] → [Worker Node] → [Results]
```

- **Orchestrator:** Küçük, her zaman ayakta olan sunucu. İş kuyruğu yönetir, EC2 açar/kapatır.
- **Worker:** EC2 instance, iş boyutuna göre tip seçilir (t3.medium → c5.4xlarge vs.). İş bitince terminate.
- **Storage:** S3 — input/output dosyalar burada. Worker oradan okur, oraya yazar.
- **UI:** Görsel pipeline builder. Modüller yapboz parçaları gibi birbirine bağlanır.

## İş Modeli

- Converter, format dönüştürücü, input/output bağlayıcı modüller → **ücretsiz**
- Pipeline modülleri → **kiralama** (abonelik veya kredi bazlı)
- Compute → **ayrıca ücretlendirilir**, iş başlamadan önce tahmini maliyet gösterilir (small/medium/large tier)

## MVP Kapsamı (Şu An Burada Odaklan)

**Tek pipeline, end-to-end çalışsın:**

1. Kullanıcı FASTQ veya BAM yükler (S3'e)
2. Sistem dosya boyutuna göre compute tier önerir + maliyet gösterir
3. Kullanıcı onaylar
4. Orchestrator uygun EC2 instance açar
5. HLA-HD çalışır
6. Sonuç (HLA allelleri) kullanıcıya döner, instance kapanır

UI bu aşamada minimal olabilir — basit form, progress bar, sonuç tablosu. Pipeline builder görsel arayüzü MVP sonrası gelir.

## Tech Stack (Öneri)

- **Backend:** Python, FastAPI
- **Job Queue:** Celery + Redis (veya başlangıç için basit PostgreSQL tabanlı)
- **Cloud:** AWS (EC2, S3, boto3)
- **Frontend:** React (başlangıçta basit, sonra görsel builder eklenecek)
- **HLA Tool:** HLA-HD (ana tool), ileride OptiType, xHLA entegrasyonu

## Domain Yol Haritası

1. **HLA / Immunogenomics** — MVP. HLA tiplendirme, peptid-MHC analizi, hastalık asosiyasyonu.
2. **Proteomics / Yapı Analizi** — AlphaFold output downstream analiz.
3. **Variant Calling / Genomics** — İleride, rekabet yoğun, öncelik düşük.

Her domain subdomain veya route prefix ile ayrılır (`/hla/`, `/proteomics/`). Mimari baştan modüler kurulur.

## Bilinen Riskler

- HLA-HD lisansı akademik kullanım için ücretsiz, ticari kullanım için iletişim gerekiyor — **lisans durumunu erken netleştir.**
- EC2 maliyet tahmini input boyutuna göre yapılacak; başlangıçta sabit tier yeterli, sonra gerçek benchmark ile kalibre edilir.
- Pipeline builder UI karmaşık bir frontend projesi — MVP'ye dahil etme, zaman kaybı.

## Feedback Döngüsü (Yakın Vadeli Eylem)

- Danışman hoca Onur Serçinoğlu ile MVP'yi göster, HLA araştırmacısı perspektifinden pain point doğrula
- RSG-Turkey üyeleri arasında potansiyel erken kullanıcı bul
- Tool lisans sorunlarını araştır
