# ORBIS

BTK HACKATHON'26 kapsamında geliştirilen ORBIS, mevzuat destekli yapay zeka asistanı ile finansal rapor üretimini aynı platformda birleştiren bir uygulamadır.

Projenin temel amacı şudur:
- Kullanıcının doğal dilde sorduğu sorulara mevzuat tabanlı yanıt verebilmek
- Kanun ve madde bazlı doğrudan arama yapabilmek
- Excel verilerinden işlevsel finansal raporlar, grafikler ve analiz çıktıları üretebilmek
- Yeni PDF kanun/veri setleri sisteme eklenerek bilgi tabanını geliştirilebilir hale getirmek

Kısacası ORBIS, bir yandan RAG destekli hukuk/mevzuat asistanı, diğer yandan finansal karar destek ve raporlama platformu olarak tasarlanmıştır.

---

## İçindekiler

1. Proje Özeti
2. Neler Yapılabilir?
3. Ürün Özellikleri
4. Teknik Mimari
5. Kullanılan Teknolojiler
6. Klasör Yapısı
7. Kurulum
8. Uygulamayı Çalıştırma
9. RAG ve ChromaDB Kullanımı
10. Yeni PDF / Kanun Ekleme
11. Metadata Standardı
12. Kanun + Madde Retrieval
13. Eski Chroma Metadata Migration
14. Testler
15. Geliştirme Notları
16. Ekip ve Hackathon Bağlamı

---

## Proje Özeti

ORBIS iki ana problemi çözmeyi hedefler:

### 1. Mevzuata Erişim Problemi
Kullanıcılar çoğu zaman belirli bir kanun maddesini hızla bulmak, bir kavramın mevzuattaki karşılığını öğrenmek veya belirli bir hukuki çerçevede soru sormak ister. ORBIS bu ihtiyacı, yerel vector database üzerinde çalışan bir RAG altyapısı ile karşılar.

### 2. Finansal Veriden Anlamlı Çıktı Üretme Problemi
İşletmeler, mali müşavirler veya analiz ekipleri Excel verilerinden düzenli ve açıklanabilir çıktılar üretmek ister. ORBIS bu noktada rapor, grafik ve analiz üretim kabiliyeti sunar.

Bu iki katman tek bir kullanıcı deneyiminde birleşir:
- sohbet arayüzü
- mevzuat tabanlı soru-cevap
- dosya yükleme
- rapor üretimi
- kaynak gösterimi

---

## Neler Yapılabilir?

Bu projeyle şu işlemler yapılabilir:

### RAG / Mevzuat Tarafı
- Kanun PDF'lerini parse edip chunk'lara ayırmak
- Chunk'lar için embedding üretmek
- Embedding'leri local ChromaDB'ye kaydetmek
- Yeni kanun PDF'leriyle bilgi tabanını genişletmek
- Kullanıcının mevzuat sorularını semantic retrieval ile yanıtlamak
- Doğrudan kanun + madde sorgularını yakalamak
- Yanıtlarda kullanılan kaynakları kullanıcıya göstermek

Örnek sorgular:
- `Vergi Usul Kanunu 359. maddeyi getir`
- `KVKK madde 11`
- `6102 sayılı kanunun 64. maddesi`
- `Gelir vergisinden kimler muaf olabilir?`

### Finansal Raporlama Tarafı
- Excel verilerinden finansal rapor üretmek
- Grafik üretmek
- Analiz çıktıları üretmek
- Sohbet ekranı üzerinden artifact generation başlatmak
- Üretilen çıktıları indirilebilir dosya olarak sunmak

Desteklenen örnek çıktılar:
- Gelir Gider Raporu
- Nakit Akış Raporu
- Borç-Alacak Raporu
- KDV Özet Raporu
- Personel Gider Analiz Raporu
- Satış Performans Raporu
- Nakit Bazlı Karlılık Raporu
- Cari Hesap Takip Raporu
- Maaş ve Personel Maliyet Raporu
- Stok Maliyet Raporu
- Vergi Hesaplama Raporu
- Grafik çıktıları
- Analiz PDF çıktıları

---

## Ürün Özellikleri

### 1. Sohbet Tabanlı Kullanım
Kullanıcı doğal dilde soru sorabilir veya artifact üretim modu seçerek rapor/grafik/analiz başlatabilir.

### 2. Retrieval-Augmented Generation
Sistem cevap üretirken mevzuat bilgisini ChromaDB üzerinden çeker ve LLM'i bağlamlandırarak kullanır.

### 3. Geliştirilebilir Bilgi Tabanı
Projeyi fork eden geliştirici kendi PDF kanun setlerini `rag_preprocess` pipeline'ına vererek veritabanını genişletebilir.

### 4. Kaynak Görünürlüğü
RAG cevaplarında kullanılan kaynaklar kullanıcı arayüzünde açılır/kapanır biçimde gösterilir.

### 5. Doğrudan Kanun + Madde Erişimi
Semantic aramaya ek olarak exact metadata / filter bazlı retrieval yeteneği vardır.

### 6. Modüler Mimari
RAG, retrieval, preprocessing, backend API, frontend ve raporlama katmanları birbirinden ayrılmıştır.

---

## Teknik Mimari

Proje temel olarak iki büyük katmandan oluşur:

### Frontend
- Next.js tabanlı kullanıcı arayüzü
- sohbet ekranı
- dosya yükleme
- artifact üretim arayüzü
- kaynak görüntüleme

### Backend
- FastAPI tabanlı unified API
- chatbot endpoint'leri
- RAG retrieval endpoint'leri
- rapor üretim endpoint'leri
- session / auth / sqlite yönetimi

### RAG Veri Akışı

```text
PDF -> parse -> clean -> article extraction -> chunking -> metadata -> embedding -> ChromaDB
```

### RAG Sorgu Akışı

```text
Kullanıcı sorusu
-> intent benzeri query parsing
-> exact madde arama / metadata filter
-> semantic retrieval fallback
-> LLM answer generation
-> kaynakların kullanıcıya sunulması
```

### Finansal Rapor Akışı

```text
Excel / kullanıcı promptu
-> parse / normalize
-> report selection
-> deterministic hesaplama
-> output generation
-> download edilebilir artifact
```

---

## Kullanılan Teknolojiler

### Backend
- `FastAPI`: API katmanı
- `Uvicorn`: ASGI server
- `python-dotenv`: ortam değişkenleri
- `pydantic`: veri modelleri
- `requests`: servis çağrıları
- `bcrypt`: parola hashleme
- `sqlite3`: yerel veritabanı

### RAG ve Yapay Zeka
- `ChromaDB`: local vector database
- `FlagEmbedding`: embedding üretimi
- `BAAI/bge-m3`: embedding modeli
- `google-genai`: cevap üretimi için LLM istemcisi

### Veri İşleme ve Raporlama
- `pandas`: veri işleme
- `openpyxl`: Excel işlemleri
- `xlsxwriter`: Excel output
- `matplotlib`: grafik üretimi
- `reportlab`: PDF/rapor çıktıları

### Frontend
- `Next.js 16`
- `React 19`
- `TypeScript`
- `Tailwind CSS`
- `lucide-react`
- `react-markdown`
- `remark-gfm`

### Veritabanı / Uygulama Katmanı
- `Prisma`
- `better-sqlite3`

---

## Klasör Yapısı

```text
btkAPP/
|-- backend/                 # Unified backend (chatbot, rag, reports)
|-- frontend/                # Next.js kullanıcı arayüzü
|-- rag_preprocess/          # PDF -> chunk -> embedding pipeline
|-- law_rag/                 # Ortak RAG yardımcı modülleri
|-- chroma_local_kanun_db/   # Local ChromaDB
|-- storage/                 # Output, metadata, backup vb.
|-- docs/                    # Teknik dokümanlar
|-- dev.db                   # SQLite veritabanı
|-- README.md
```

### Önemli dizinler

#### `backend/`
Chatbot, RAG ve rapor servislerinin bulunduğu ana backend katmanıdır.

#### `frontend/`
Sohbet ekranı, artifact üretim ekranı ve kullanıcı deneyimi burada yer alır.

#### `rag_preprocess/`
Kanun PDF'lerinin işlenip chunk ve embedding üretildiği pipeline burada bulunur.

#### `law_rag/`
Chroma yönetimi, metadata standardizasyonu, duplicate kontrolü, query parsing ve retrieval yardımcıları burada yer alır.

#### `chroma_local_kanun_db/`
Mevzuat embedding’lerinin tutulduğu local vector database dizinidir.

---

## Kurulum

### Gereksinimler
- Python 3.11+
- Node.js 18+
- npm

### 1. Repoyu indirin

```powershell
git clone <repo-url>
cd btkAPP
```

### 2. Python sanal ortamı oluşturun

```powershell
python -m venv venv
.\venv\Scripts\python -m pip install --upgrade pip
.\venv\Scripts\pip install -r backend/requirements.txt
```

### 3. Frontend bağımlılıklarını kurun

```powershell
cd frontend
npm install
npx prisma generate
cd ..
```

### 4. Ortam değişkenlerini hazırlayın

Kök dizinde `.env`:

```env
DATABASE_URL="file:./dev.db"
GOOGLE_API_KEY="your-google-api-key"
JWT_SECRET="replace-with-a-local-secret"
BACKEND_API_URL="http://localhost:8000"
RAG_API_URL="http://localhost:8000"
CHROMA_DB_PATH="./chroma_local_kanun_db"
CHROMA_COLLECTION_NAME="kanun_embedding"
CHROMA_MIGRATION_BACKUP_DIR="./storage/chroma_backups"
EMBEDDING_MODEL_NAME="BAAI/bge-m3"
LAW_ALIASES_JSON="{\"VUK\":\"Vergi Usul Kanunu\",\"TTK\":\"Turk Ticaret Kanunu\",\"TCK\":\"Turk Ceza Kanunu\",\"KVKK\":\"Kisisel Verilerin Korunmasi Kanunu\"}"
REPORT_GEN_API_URL="http://localhost:8000"
```

`frontend/.env`:

```env
DATABASE_URL="file:../dev.db"
BACKEND_API_URL="http://localhost:8000"
```

---

## Uygulamayı Çalıştırma

Bu projeyi lokal ortamda çalıştırmak için iki terminal yeterlidir.

### Terminal 1: Backend

```powershell
cd backend
..\venv\Scripts\python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Bu servis şunları ayağa kaldırır:
- chatbot API
- RAG retrieval API
- rapor / grafik / analiz üretim API

Sağlık kontrolü:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/health/rag
```

### Terminal 2: Frontend

```powershell
cd frontend
npm run dev
```

Tarayıcı:

```text
http://localhost:3000
```

---

## RAG ve ChromaDB Kullanımı

Sistem mevzuat bilgisini local ChromaDB üzerinden kullanır.

Varsayılan ayarlar:
- DB path: `./chroma_local_kanun_db`
- collection: `kanun_embedding`

RAG tarafında amaç:
- kanun PDF’lerini vektörleştirmek
- semantic retrieval ile bağlam toplamak
- gerektiğinde doğrudan madde bazlı filtreli arama yapmak

---

## Yeni PDF / Kanun Ekleme

Bu projenin önemli özelliklerinden biri, yeni mevzuat PDF’lerinin sisteme kolayca eklenebilmesidir.

### Çalışma mantığı

`rag_preprocess` artık şu akışı tamamlar:

```text
PDF -> parse -> chunk -> metadata -> embedding -> ChromaDB append
```

### Kullanım

PDF’leri bir klasöre koyun ve şu komutu çalıştırın:

```powershell
.\venv\Scripts\python -m rag_preprocess --input-dir .\docs\my_laws
```

GUI ile klasör seçmek isterseniz:

```powershell
.\venv\Scripts\python -m rag_preprocess
```

### Davranış
- overwrite yapmaz
- mevcut collection mantığını korur
- yeni verileri append eder
- duplicate `id` ve `content_hash` kontrolü yapar

### Oluşan çıktılar
- `output/parsed_json/`
- `output/chunks_jsonl/`
- `output/quality_reports/`
- `output/logs/`

---

## Metadata Standardı

Yeni ingestion sürecinde her chunk için düz, JSON-serializable ve filter-friendly metadata üretilir.

Örnek:

```json
{
  "document_name": "Vergi Usul Kanunu",
  "source_file": "213.pdf",
  "kanun_adi": "Vergi Usul Kanunu",
  "kanun_no": "213",
  "kanun_adi_normalized": "VERGI USUL KANUNU",
  "madde_no": "359",
  "section": "Ucuncu Bolum",
  "chunk_index": 12,
  "page": 5,
  "embedding_model": "BAAI/bge-m3",
  "created_at": "2026-05-19T17:00:00+00:00",
  "content_type": "law",
  "language": "tr",
  "content_hash": "..."
}
```

Bu metadata yapısı şu avantajları sağlar:
- exact filter araması
- kanun adı normalizasyonu
- madde bazlı arama
- kaynak gösterimi
- migration uyumluluğu

---

## Kanun + Madde Retrieval

Sistem artık yalnızca semantic arama değil, doğrudan mevzuat maddesi çağırma yeteneği de içerir.

Örnek sorgular:
- `Vergi Usul Kanunu 359. maddeyi getir`
- `TCK 125'i göster`
- `KVKK madde 11`
- `6102 sayılı kanunun 64. maddesi`

### Retrieval sırası

1. exact metadata search
2. metadata filter search
3. ilgili kanun içinde semantic fallback
4. genel semantic retrieval

### Alias desteği

Desteklenen örnek kısaltmalar:
- `VUK`
- `TTK`
- `TCK`
- `KVKK`

Bu liste `LAW_ALIASES_JSON` ile genişletilebilir.

---

## Eski Chroma Metadata Migration

Var olan eski kayıtların metadata yapısını yeni standarda yaklaştırmak için migration scripti eklenmiştir.

### Migration çalıştırma

```powershell
.\venv\Scripts\python -m law_rag.migrate_chroma_metadata
```

### Rollback

```powershell
.\venv\Scripts\python -m law_rag.migrate_chroma_metadata --restore-from-backup .\storage\chroma_backups\chroma_local_kanun_db_YYYYMMDDTHHMMSSZ
```

### Güvenlik
- önce backup alınır
- sonra metadata update edilir
- gerekirse rollback yapılabilir

---

## Testler

Örnek test komutları:

```powershell
.\venv\Scripts\python -m pytest backend/tests/test_law_rag_features.py
```

Bu testler şunları hedefler:
- metadata standardizasyonu
- duplicate detection
- kanun/madde query parsing
- exact metadata retrieval

Genel backend davranışı için ayrıca proje içindeki diğer test dosyaları da çalıştırılabilir.

---

## Geliştirme Notları

### Mevcut tasarım ilkeleri
- mevcut chatbot akışı korunur
- mevcut retrieval mimarisi bozulmaz
- vector DB kullanımı korunur
- ingestion pipeline geliştirilebilir tutulur
- path’ler mümkün olduğunca config/env üzerinden yönetilir

### RAG cevapları
- kaynaklar kullanıcıya gösterilir
- retrieval tarafı semantic + metadata tabanlı hibrit şekilde çalışır

### Finansal raporlar
- deterministic hesaplama yaklaşımı tercih edilir
- veri dönüşümü ve çıktı üretimi backend’de kontrollü biçimde yapılır

---

## Kullanım Senaryoları

### Senaryo 1: Mevzuat sorusu
Kullanıcı sohbet ekranında:

```text
KVKK madde 11
```

Sistem:
- sorguyu parse eder
- metadata filter ile uygun maddeyi bulur
- cevabı döner
- kullanılan kaynakları gösterir

### Senaryo 2: Yeni kanun ekleme
Geliştirici:
- yeni PDF’leri bir klasöre koyar
- `rag_preprocess` çalıştırır
- yeni embedding’ler ChromaDB’ye eklenir

### Senaryo 3: Finansal artifact üretimi
Kullanıcı:
- artifact modunu seçer
- Excel yükler
- rapor/grafik/analiz üretir
- çıktıyı indirir

---

## Ekip ve Hackathon Bağlamı

Bu proje, BTK HACKATHON'26 kapsamında geliştirildi.

Hackathon bağlamında hedeflenen değer önerisi:
- mevzuat erişimini hızlandırmak
- kullanıcıların doğal dilde bilgi almasını sağlamak
- finansal veriden hızlı, somut ve indirilebilir çıktılar üretmek
- geliştirilebilir bir bilgi tabanı mimarisi sunmak

Bu yönüyle ORBIS yalnızca bir chatbot değil; mevzuat, retrieval, veri işleme ve raporlama katmanlarını tek çatı altında birleştiren modüler bir platform prototipidir.

---

## Hızlı Başlangıç

Kısa özet:

```powershell
python -m venv venv
.\venv\Scripts\python -m pip install --upgrade pip
.\venv\Scripts\pip install -r backend/requirements.txt

cd frontend
npm install
npx prisma generate
cd ..
```

Backend:

```powershell
cd backend
..\venv\Scripts\python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
cd frontend
npm run dev
```

Yeni PDF eklemek için:

```powershell
.\venv\Scripts\python -m rag_preprocess --input-dir .\docs\my_laws
```

---

## Lisans / Not

Bu README, projeyi hem son kullanıcı hem jüri hem de geliştirici gözüyle anlaşılır kılmak amacıyla hazırlanmıştır. İstenirse bir sonraki adımda buna ekran görüntüsü bölümü, API endpoint tablosu ve demo akış diyagramı da eklenebilir.
