# Report Table Generator - Detayli Proje Dokumantasyonu

Bu dokuman, `report_table_generator` projesinin bugunku durumunu cok detayli sekilde anlatir. Amaci sadece "hangi dosya ne ise yariyor" sorusunu cevaplamak degil; ayni zamanda projenin mimarisini, veri akislarini, rapor mantiklarini, sonradan yaptigimiz finansal dogruluk iyilestirmelerini ve aktif/legacy katman ayrimini netlestirmektir.

Bu belge ozellikle su uc soruya cevap verir:

1. Bu proje tam olarak ne yapiyor?
2. Hangi modul hangi sorumluluga sahip?
3. Su ana kadar projede hangi gelistirmeleri yaptik ve bunlar neden onemli?

Not:

- Bu dokuman kodun mevcut snapshot'ini anlatir.
- Projede hem yeni `reports/*.py` tabanli "structured_financial" mimarisi, hem de eski `report_handlers/*.py` tabanli legacy akisi birlikte bulunur.
- Finansal hesaplamalar icin tasarim ilkesi nettir: LLM karar verir, esleme yapar ve anlamlandirmaya yardim eder; hesaplamayi Python + pandas + Decimal yapar.

---

## 1. Projenin Ana Amaci

Bu proje, kullanicidan ya Excel dosyasi ya da belirli durumlarda dogal dil/prompt alarak finansal raporlar ureten bir CLI uygulamasidir.

Projenin temel hedefleri:

- farkli Excel kolon adlarini ortak bir veri kontratina normalize etmek
- secilen rapor tipine gore deterministic hesaplama yapmak
- warning, validation ve audit izlerini kaybetmeden rapor uretmek
- JSON ve Excel ciktilarini birlikte vermek
- finans ekiplerinin kullanabilecegi, ERP/muhasebe mantigina yakin raporlar olusturmak

Bugun itibariyla sistem 11 farkli rapor tipini destekler:

| Report ID | Ekran Adi | Amac |
|---|---|---|
| `income_expense_report` | Gelir Gider Raporu | gelir, gider ve net sonuc ozeti |
| `cash_flow_report` | Nakit Akis Raporu | gunluk/net/kumulatif nakit akis analizi |
| `debt_receivable_report` | Borc-Alacak Raporu | cari bazli borc, alacak, risk ve vade takibi |
| `vat_summary_report` | KDV Ozet Raporu | satis/alis KDV ozetleri |
| `personnel_expense_report` | Personel Gider Analiz Raporu | departman/personel bazli maliyet analizi |
| `sales_performance_report` | Satis Performans Raporu | urun, musteri, satisci ve trend analizi |
| `profitability_report` | Nakit Bazli Karlilik Raporu | gelir-gider uzerinden nakit bazli sonuc |
| `current_account_report` | Cari Hesap Takip Raporu | acik borc/alacak ve aging analizi |
| `payroll_cost_report` | Maas ve Personel Maliyet Raporu | net maas, vergi, SGK ve toplam isveren maliyeti |
| `inventory_cost_report` | Stok Maliyet Raporu | weighted average maliyet ve kalan stok |
| `tax_calculation_report` | Vergi Hesaplama Raporu | vergi turu ve donem bazli vergi analizi |

---

## 2. Bu Projede Su Ana Kadar Neleri Gelistirdik?

Bu bolum, projede yaptigimiz gelistirmelerin ozet tarihcesidir. Buradaki maddeler, sistemin bugunku halini anlamak icin kritiktir.

### 2.1 Finansal Hesaplar Deterministic Hale Getirildi

Ilk temel karar, LLM'in hesaplama yapmamasiydi. Bunun sonucu olarak:

- tum finansal hesaplar pandas/Python tarafina tasindi
- kullanicidan gelen hazir toplam kolonlari "advisory" kabul edildi
- gerekli alanlar her zaman tekrar hesaplanir hale geldi
- hesaplanan deger ile input deger farkliysa warning uretilip sistem hesaplanan degeri kullanmaya basladi

Bu karar; vergi, personel maliyeti, satis tutari, stok degeri gibi kritik alanlarda auditability sagladi.

### 2.2 Decimal Tabanli Finansal Hesap Katmani Eklendi

Float kaynakli kurus hatalarini azaltmak icin:

- `utils/money_utils.py` merkezli `Decimal` kullanimi getirildi
- `quantize_money`, `compare_money_values`, `calculate_tax_amount`, `calculate_total_employer_cost` gibi helper'lar eklendi
- mismtach toleransi config uzerinden yonetilir hale geldi
- JSON export oncesi `Decimal -> float` donusumu kontrollu hale getirildi

### 2.3 Typed Settings ve Config-Driven Finansal Kurallar Eklendi

`config.py` artik sadece `.env` okuyucu degil; proje davranisini yoneten bir settings katmanidir.

Buraya tasinan kurallar:

- default timezone
- default currency
- employer SGK oranı
- mismatch toleransi
- strict inventory validation
- cost method
- masking davranisi
- report/calculation version bilgisi

Boylece hardcoded finansal sabitler azaltildi.

### 2.4 Structured Warning Sistemi Kuruldu

Eskiden warning'ler cogunlukla string listesi gibiydi. Simdi warning'ler structured object olarak tasiniyor.

Bir warning artik su bilgileri tasiyabiliyor:

- `type`
- `severity`
- `message`
- `row`
- `field`
- `input_value`
- `calculated_value`
- `action`
- `audit_run_id`
- `calculated_from`
- `lineage`

Bu sistem sayesinde:

- frontend highlight icin gerekli veri hazirlandi
- hangi satirin neden degistigi veya dustugu gorulebilir oldu
- warning severity ozetleri uretilmeye baslandi
- `execution_status` hesaplanabilir hale geldi

### 2.5 Audit Metadata Katmani Eklendi

Her rapor calismasi artik audit metadata ile tasiniyor:

- `audit_run_id`
- `generated_at`
- `report_version`
- `calculation_version`
- `timezone`
- `reporting_currency`

Bu bilgiler warning'lere de propagate edilir. Boylece ayni batch icindeki warning'ler ile output ayni audit calismasina baglanabilir.

### 2.6 Timezone-Aware Tarih Normalizasyonu Eklendi

`utils/date_utils.py` timezone-aware hale getirildi.

Kazanimlar:

- naive datetime degerleri canonical timezone ile localize edilir
- UTC/offset iceren degerler canonical timezone'a convert edilir
- `period` ve `month` derivation timezone normalize edilmis tarihlerden uretilir
- invalid timezone durumunda warning uretilir ve default timezone kullanilir

Varsayilan timezone:

```text
Europe/Istanbul
```

### 2.7 Multi-Currency Foundation Eklendi

Proje artik farkli para birimlerini sessizce toplamamaya calisir.

Temel davranis:

- currency kolonu normalize edilir
- farkli currency'ler tespit edilirse `mixed_currency_detected=True`
- scalar summary alanlari gerekirse `None` olur
- `totals_by_currency` gibi alanlar kullanilir
- conversion henuz yapilmaz; onun yerine critical warning uretilir

### 2.8 PII / Security Foundation Eklendi

`utils/security_utils.py` ile:

- IBAN maskesi
- vergi/TCKN/VKN benzeri alanlarin maskelenmesi
- personel ismi maskelenmesi

debug/export tarafinda opsiyonel hale getirildi.

### 2.9 Rapor Bazli Kritik Finansal Duzeltmeler Yapildi

Bu projedeki en buyuk gelistirme grubu rapor bazli finansal dogruluk duzeltmeleridir:

- Personel gider raporunda `employer_cost` ile `total_employer_cost` ayrildi.
- Payroll raporunda toplam isveren maliyeti her zaman deterministic hesaplanmaya baslandi.
- Cari hesap raporunda acik borc/acik alacak/net acik pozisyon ayrildi; paid satirlar aging disina cikarildi.
- Borc-alacak raporunda `counterparty_type` bazli risk mantigi eklendi; ayrica `debt_amount/receivable_amount` kolonlarindan `amount/direction` turetme hatasi duzeltildi.
- Satis raporunda gross sales / refund / net sales ayrimi netlestirildi; `return_status` ile `transaction_type` karismasi onlendi.
- Karlilik raporu "Nakit Bazli Karlilik" olarak netlestirildi ve `accounting_profit=None` future-proof alani eklendi.
- Stok maliyet raporu weighted-average mantigina sabitlendi; `inventory_key` standardi ve movement-summary tutarliligi saglandi.
- KDV ve vergi hesap raporlarinda `0.20` ile `20` oran formatlari normalize edildi.

### 2.10 Test Kapsami Buyutuldu

`tests/test_mvp_pipeline.py` dosyasi artik yalnizca smoke test degil, sistemin finansal davranisini koruyan regression setidir.

Test edilen basliklar:

- registry ve rapor listesi
- mapping alias duzeltmeleri
- personel/payroll deterministic hesaplari
- vergi oran normalizasyonu
- satis refund ve return_status akislari
- inventory weighted average ve negative stock
- current account aging mantigi
- debt receivable risk ve split amount turetme
- Decimal precision
- masking
- mixed currency
- warning schema ve audit metadata

---

## 3. Sistemin Aktif Calisma Akisi

Bir Excel bazli rapor uretim akisi bugun su sekilde calisir:

1. `main.py`
   Kullanici rapor tipini ve input tipini secer.
2. `agents/excel_preview_agent.py`
   Excel preview JSON olusturulur.
3. `agents/llm_mapping_agent.py`
   LLM mapping denemesi yapilir.
4. `validators/mapping_validator.py`
   Mapping JSON strict schema ile dogrulanir.
5. `agents/heuristic_mapping_agent.py`
   LLM mapping basarisizsa fallback mapping uretilir.
6. `utils/mapping_utils.py`
   Mapping sanitize edilir, alias/fallback kurallari uygulanir.
7. `agents/excel_parsing_agent.py`
   Secilen sheet tam parse edilir.
8. `services/report_execution_service.py`
   Normalize akisi baslatilir.
9. `reports/base_agent.py` veya `normalizers/transaction_normalizer.py`
   Rapor tipine gore normalize edilir.
10. `validators/transaction_validator.py`
    Report-specific validation calisir.
11. `reports/<rapor>.py` veya legacy `report_handlers/*`
    Deterministic hesaplama ve rapor olusumu yapilir.
12. `outputs/output_generator.py`
    JSON ve Excel ciktilari uretilir.

Prompt akisi ise daha kisa yol izler:

1. `agents/prompt_parsing_agent.py`
   prompt kayitlara donusturulur
2. `validators/transaction_validator.py`
   validation yapilir
3. report execution ve output asamalarina gecilir

---

## 4. Aktif Mimari ile Legacy Mimari Arasindaki Fark

Projede iki farkli rapor yurutme modeli vardir.

### 4.1 Structured Financial Mimari

Bu yeni ve bugun agirlikli olarak kullandigimiz yapidir.

Ozellikleri:

- `reports/*.py` dosyalarindaki `ReportAgent` siniflarini kullanir
- `reports/base_agent.py` uzerinden ortak davranis alir
- warning, metadata, Decimal, audit, timezone, currency kurallariyla daha uyumludur
- her rapor validate ve generate adimlarini kendi icinde acikca kontrol eder
- Excel export icin genellikle `utils/excel_writer.py` kullanir

Bu gruptaki raporlar:

- `debt_receivable_report`
- `vat_summary_report`
- `personnel_expense_report`
- `sales_performance_report`
- `profitability_report`
- `current_account_report`
- `payroll_cost_report`
- `inventory_cost_report`
- `tax_calculation_report`

### 4.2 Legacy Transaction Mimari

Bu daha eski akistir.

Ozellikleri:

- `report_handlers/*.py` kullanir
- normalize asamasinda `normalizers/transaction_normalizer.py` devreye girer
- tablo/metric/chart yaklasimi eski nesildir
- `outputs/sheet_builders.py`, `outputs/style_manager.py`, `outputs/chart_factory.py` ile daha "sunum odakli" workbook uretir

Bu gruptaki raporlar:

- `income_expense_report`
- `cash_flow_report`

Bu ayrim, projeyi okuyan gelistirici icin cok onemlidir. Ayni klasorde iki farkli nesil mimari birlikte bulunmaktadir.

---

## 5. Dizin Haritasi

```text
report_table_generator/
├── main.py
├── config.py
├── requirements.txt
├── PROJE_MODUL_DOKUMANTASYONU.md
├── agents/
├── normalizers/
├── outputs/
├── reports/
├── report_handlers/
├── services/
├── utils/
├── validators/
├── scripts/
├── tests/
└── core/   (su anda bos / placeholder)
```

---

## 6. Moduller ve Dosyalar - Klasor Bazli Detayli Aciklama

## 6.1 Root Dosyalari

| Dosya | Gorev | Detay |
|---|---|---|
| `main.py` | CLI orkestratoru | Kullanici secimlerini alir, intent yaratir, Excel veya prompt akisini secip preview -> mapping -> normalize -> validate -> generate -> output zincirini calistirir. |
| `config.py` | Settings katmani | `.env` degerlerini typed settings objesine cevirir. Finansal oranlar, timezone, currency, masking ve version bilgisi buradan gelir. |
| `requirements.txt` | Bagimlilik listesi | pandas, openpyxl, matplotlib, xlsxwriter, python-dotenv, google-genai gibi kutuphaneleri tanimlar. |
| `PROJE_MODUL_DOKUMANTASYONU.md` | Bu belge | Projenin guncel teknik ve fonksiyonel dokumani. |
| `core/` | Placeholder | Su anda aktif kod yok; ileride ortak domain modelleri veya engine katmani icin ayrilmis gorunur. |

### `main.py` ayrintisi

`main.py` projenin "insanla ilk temas eden" dosyasidir. Temel sorumluluklari:

- rapor secimi menusu gostermek
- input tipi secimini yaptirmak
- GUI file picker ile Excel sectirmek
- CLI warning/error mesajlarini formatlamak
- mapping fallback zincirini yonetmek
- validation sonucu veri kalmadiysa temiz sekilde durmak
- ciktilarin dosya yollarini kullaniciya gostermek

Kritik detay:

- `sanitize_mapping_for_report()` burada cagirilir. Bu, mapping agent bazen yanlis alan secse bile report-specific emniyet kemeri saglar.

---

## 6.2 `agents/` Klasoru

| Dosya | Gorev | Aktiflik |
|---|---|---|
| `agents/excel_preview_agent.py` | Excel'in tamamini degil yapisini anlatan preview JSON uretir | aktif |
| `agents/excel_parsing_agent.py` | Secilen sheet'i tam parse eder | aktif |
| `agents/heuristic_mapping_agent.py` | LLM mapping basarisizsa alias ve kolon tiplerine gore fallback mapping uretir | aktif |
| `agents/llm_mapping_agent.py` | LLM'e strict schema ile mapping JSON urettirir | aktif |
| `agents/prompt_parsing_agent.py` | Prompt'tan intent ve kayit listesi cikarmaya calisir | aktif |
| `agents/report_generator_agent.py` | `ReportExecutionService` icin ince facade | aktif |

### `excel_preview_agent.py`

Bu modulun amaci, buyuk Excel dosyasini LLM'e oldugu gibi gondermemektir. Bunun yerine:

- sheet sayisini
- kolon adlarini
- ornek satirlari
- numeric/date/text kolon tiplerini
- header row tahminini

ozetleyerek preview JSON olusturur.

Bu hem maliyeti dusurur hem LLM'in daha kontrollu karar vermesini saglar.

### `heuristic_mapping_agent.py`

Bu modul, projenin "LLM yoksa da calis" mekanizmasidir. Alias esleme yapar, uygun sheet'i secer ve:

- `column`
- `derived`
- `constant`
- `not_available`
- `llm_infer_later`

mapping tiplerinden birini secerek fallback mapping JSON uretir.

### `llm_mapping_agent.py`

Bu modul LLM prompt ve JSON schema tarafini yonetir. En kritik ilke sunudur:

- LLM hesaplama yapmaz
- sadece kolon esleme yapar
- sadece preview icindeki kolonlari kullanir
- strict schema disina cikamaz

### `prompt_parsing_agent.py`

Bu modul hem intent olusturur hem de prompt icindeki veriyi parse etmeye calisir.

Destekledigi prompt formatlari:

- JSON object/list
- delimiter tabanli tablo
- key-value bloklari

Bu modulun fonksiyonu tam NLU degil; daha cok "kullanici promptunu report inputuna donusturme" katmanidir.

---

## 6.3 `services/` Klasoru

| Dosya | Gorev | Not |
|---|---|---|
| `services/report_registry_service.py` | Tum rapor template'lerini ve handler class'larini yukler | aktif omurga |
| `services/report_execution_service.py` | Normalize ve generate akisini dogru handler'a yonlendirir | aktif omurga |
| `services/report_suitability_service.py` | Bu veri bu rapora uygun mu sorusunu cevaplar | aktif |
| `services/llm_service.py` | Google GenAI istemcisi ve JSON generation wrapper'i | aktif, API key bagimli |
| `services/ai_analysis_service.py` | Rapor sonucu uzerinden kisa AI yorumu uretme altyapisi | hazir ama merkezi akista aktif degil |
| `services/localization_service.py` | Legacy workbook icin sabit label/disclaimer metinleri | destekleyici |

### `report_registry_service.py`

Bu servis:

- `reports/index.json` okur
- template'leri yukler
- `handler_class` string'lerini import eder
- rapor tanimlarinin tekil oldugunu garanti eder

Tum sistemin rapor listesi buradan cikar.

### `report_execution_service.py`

Bu servis aktif mimarinin merkezidir.

Iki farkli seyi yapar:

1. `normalize_for_report()`
   ham veriyi secilen raporun bekledigi inputa cevirir
2. `generate_report()`
   validated inputtan rapor nesnesini uretir

En kritik kararlar burada verilir:

- handler `generate/validate` mi kullaniyor?
- yoksa eski `compute/render_payload` yoluna mi gidecek?
- input warnings ile validation warnings nasil birlestirilecek?

### `report_suitability_service.py`

Bu servis "yanlis rapor secilirse" kullaniciyi korur.

Kontrol ettigi seyler:

- secilen input tipi destekleniyor mu?
- mapping'te zorunlu alanlar bulundu mu?
- mapping preview kolonlarina referans veriyor mu?
- normalize edilen payload rapor icin anlamsiz mi?
- alternatif rapor var mi?

### `llm_service.py`

Bu servis Google GenAI client'ini kapsuller. Tasarim hedefi:

- LLM kullanan katmanlarin API detayina bagimliligini azaltmak
- JSON schema kontrollu cevap almak

### `ai_analysis_service.py`

Bu servis rapor summary'sinden kisa yapay zeka yorumu uretmeyi hedefler. Altyapi mevcuttur ama mevcut structured_financial akista merkezi bir zorunlu adim degildir. Yani proje bunu barindirir ama her rapor akisi fiilen buna bagimli degildir.

### `localization_service.py`

Legacy Excel workbook katmaninda kullanilan:

- disclaimer metinleri
- field label'lari
- sheet adlari
- metric type etiketleri

gibi sabitleri tutar.

---

## 6.4 `validators/` Klasoru

| Dosya | Gorev |
|---|---|
| `validators/mapping_validator.py` | mapping JSON schema'sini dogrular |
| `validators/transaction_validator.py` | normalized payload'i report-specific validate eder |

### `mapping_validator.py`

Bu dosya LLM mapping sonucunu ciddiye almadan once strict kontrol yapar:

- `mapping_type` gecerli mi?
- `rule_type` gecerli mi?
- `source_columns` yapisi dogru mu?
- `status=passed` iken zorunlu alanlar map edildi mi?
- `not_available` zorunlu alanlarda kullanilmis mi?

Boylece LLM'in "guvenle calisabilir" JSON uretmesi zorunlu hale gelir.

### `transaction_validator.py`

Bu dosya iki farkli role sahiptir:

- yeni report agent'leri icin `handler.validate()` cagirisini orkestre eder
- legacy path icin fallback validation saglar

Ayrica:

- warning'leri normalize eder
- `warning_summary` uretir
- `execution_status` hesaplar
- audit context'i response'a ekler

---

## 6.5 `normalizers/` Klasoru

| Dosya | Gorev | Mimari |
|---|---|---|
| `normalizers/mapping_rule_builder.py` | derived mapping rule'larini runtime kuralina cevirir | legacy/transaction |
| `normalizers/transaction_normalizer.py` | mapping JSON + Excel row -> standart transaction listesi | legacy/transaction |

### Bu klasor neden var?

Yeni raporlar kendi `ReportAgent.normalize()` metoduyla ilerler. Ama `income_expense_report` ve `cash_flow_report` gibi eski transaction tabanli raporlar hala bu katmani kullanir.

Yani bu klasor:

- aktif ama belirli raporlarla sinirli
- yeni structured_financial raporlarin ana normalize yolu degil

---

## 6.6 `utils/` Klasoru

Bu klasor projenin en yogun ortak kodunu tasir. Bir bakima "engine" burada durur.

| Dosya | Gorev |
|---|---|
| `utils/mapping_utils.py` | ortak field listesi, alias sistemi, mapping objeleri, mapping sanitize, normalize_dataframe_for_report |
| `utils/validation.py` | common dataframe validation helper'lari |
| `utils/warning_utils.py` | structured warning uretimi, dedupe, severity ozeti |
| `utils/date_utils.py` | timezone-aware tarih parse/normalize/period helper'lari |
| `utils/money_utils.py` | Decimal tabanli para helper'lari |
| `utils/reporting_utils.py` | decimal aggregation ve currency summary helper'lari |
| `utils/security_utils.py` | PII masking helper'lari |
| `utils/audit_utils.py` | audit context ve metadata helper'lari |
| `utils/excel_writer.py` | structured_financial raporlarin sade Excel writer'i |
| `utils/excel_table_detector.py` | Excel'de header row bulma ve tablo parse etme |
| `utils/text_normalization.py` | Turkish/encoding duyarli alias normalization |
| `utils/text_numbers.py` | string -> numeric parse helper'lari |

### `mapping_utils.py`

Bu dosya projenin ortak veri sozlugudur.

Burada su tanimlar bulunur:

- `COMMON_STANDARD_FIELDS`
- `FIELD_OUTPUT_TYPES`
- `FIELD_ALIASES`
- `empty_mapping`, `column_mapping`, `derived_mapping`, `constant_mapping`
- `normalize_dataframe_for_report`
- `match_field_by_alias`
- `sanitize_mapping_for_report`

Ozellikle `sanitize_mapping_for_report()`, rapor bazli mapping hatalarina karsi runtime emniyet kemeri gorevi gorur. Son yaptigimiz satis raporu duzeltmesinde `Return Status` kolonunun yanlislikla `transaction_type` secilmesini burada otomatik onardik.

### `validation.py`

Bu dosya tum report agent'lerin tekrar tekrar ayni boilerplate'i yazmamasini saglar.

Temel islevleri:

- kolon yoksa eklemek
- row number takibi
- text/numeric/date normalize etmek
- currency/timezone defaultlarini atamak
- duplicate strategy uygulamak
- period derive etmek

### `warning_utils.py`

Bu dosya yeni warning mimarisinin kalbidir.

Buradaki en kritik kavramlar:

- severity standardi: `info`, `warning`, `critical`, `blocking`
- warning type -> default severity map'i
- warning dedupe
- `determine_execution_status()`

Bu sayede rapor sadece "hata var/yok" demiyor; hangi seviyede problem oldugunu da soyluyor.

### `date_utils.py`

Bu dosya timezone ve period dogrulugu icin kritiktir.

Burada:

- `normalize_timezone`
- `localize_naive_datetime`
- `convert_to_canonical_timezone`
- `parse_date_value`
- `derive_period_from_timezone_aware_datetime`

gibi helper'lar yer alir.

### `money_utils.py`

Bu dosya finansal dogrulugun omurgasidir.

Onemli helper'lar:

- `to_decimal`
- `quantize_money`
- `round_money`
- `compare_money_values`
- `normalize_tax_rate`
- `calculate_tax_amount`
- `calculate_total_employer_cost`
- `normalize_report_numbers_for_export`

### `reporting_utils.py`

Bu dosya daha cok aggregation katmanidir.

Temel islevler:

- `decimal_series_sum`
- `decimal_series_mean`
- `build_currency_summary`

Buradaki `build_currency_summary()`, mixed-currency detection mantiginin ortak uygulamasidir.

### `security_utils.py`

Bu dosya:

- `mask_iban`
- `mask_tax_id`
- `mask_employee_name`
- `mask_sensitive_payload`

yardimcilariyla debug/export maskelemesini merkezi hale getirir.

### `audit_utils.py`

Bu dosya:

- `create_audit_context`
- `ensure_audit_context`
- `attach_audit_run_id`
- `make_metadata`

fonksiyonlariyla audit izini tum pipeline boyunca korur.

### `excel_writer.py`

Bu dosya yeni structured_financial raporlar icin sade ve deterministic Excel writer'dir.

Ozellikleri:

- sheet bazli veri yazar
- currency/date/number formatlar uygular
- negatif sayilari farkli renkle gosterebilir
- DataFrame veya list/dict veri yapilarini destekler

### `excel_table_detector.py`

Bu dosya, kullanicinin Excel'inde baslik satirinin nerede oldugunu tahmin etmek icin vardir. Sabit satir varsayimi yapmaz; keyword ve text-likeness uzerinden header row tespit eder.

### `text_normalization.py`

Bu dosya Turkce karakter, encoding bozulmasi ve noktalama farklarini normalize ederek alias eslesmesini guclendirir. Ozellikle bozuk UTF-8 kaynakli kolon farklarinda faydalidir.

### `text_numbers.py`

Bu dosya `"1.250,50"`, `"2 milyon"`, `"3 bin"` gibi metinleri sayiya cevirmek icin kullanilir.

---

## 6.7 `outputs/` Klasoru

| Dosya | Gorev | Aktiflik |
|---|---|---|
| `outputs/output_generator.py` | final JSON ve Excel cikti orkestrasyonu | aktif |
| `outputs/sheet_builders.py` | legacy workbook/overview/charts builder | legacy ama aktif |
| `outputs/chart_factory.py` | Excel ve PNG chart helper'lari | legacy/destekleyici |
| `outputs/formatting.py` | metric/transaction Excel formatlama helper'lari | legacy/destekleyici |
| `outputs/style_manager.py` | legacy workbook stilleri | legacy/destekleyici |
| `outputs/debug_outputs/` | runtime debug artefact alanı | kod degil |
| `outputs/reports/` | olusan rapor klasorleri | kod degil |

### `output_generator.py`

Bu dosya cikti katmaninin merkezidir.

Yaptigi seyler:

- output klasoru yaratir
- warnings'i merge eder
- masking uygular
- warning summary ve execution status'i response'a yazar
- JSON payload'i serialize eder
- Excel dosyasini uretir

Onemli not:

- `write_png()` helper'i bulunur
- ancak `generate_outputs()` aktif akista su an JSON ve XLSX uretir
- yani kod tabaninda PNG altyapisi vardir ama top-level akista otomatik her zaman uretilmemektedir

### `sheet_builders.py`

Bu dosya daha gorsel, daha sunum odakli workbook sayfalari uretir. Ozellikle legacy handler'larin ciktilarinda:

- overview
- charts
- normalized data
- compact summary

sekillerinde zengin sheet'ler olusturur.

### `chart_factory.py`

Bu dosya:

- Excel chart nesneleri olusturur
- fallback chart secimi yapar
- gerekirse PNG chart kaydeder

Chart altyapisi daha cok legacy raporlarda on plandadir.

### `formatting.py` ve `style_manager.py`

Bu iki dosya daha cok:

- metric kartlari
- tablo stilleri
- sayi/para yuzde formatlama
- workbook renk paleti

gibi gorsel konulari kapsar.

---

## 6.8 `reports/` Klasoru

Bu klasor yeni nesil rapor agent'lerini ve tum report template'lerini tutar.

### Ortak dosyalar

| Dosya | Gorev |
|---|---|
| `reports/base_agent.py` | yeni report mimarisinin ortak tabani |
| `reports/index.json` | tum report template referanslari |
| `reports/__init__.py` | package marker |

### `base_agent.py`

Bu sinif yeni rapor mimarisinin ortak omurgasidir. Sagladigi ortak davranislar:

- `normalize()`
- `finalize_validation_result()`
- `build_result()`
- `export_excel()`

Tum structured_financial raporlar warning, metadata, summary sayaçlari ve sheet spec formatini bu ortak taban uzerinden standardize eder.

### Rapor dosyalari ve ne yaptiklari

| Dosya | Raporun Amaci | Kritik Hesap / Duzeltme |
|---|---|---|
| `reports/debt_receivable_report.py` | cari bazli borc-alacak, risk ve vade raporu | `counterparty_type` bazli risk, `debt_amount/receivable_amount -> amount/direction` turetme, overdue debt/receivable ayirimi |
| `reports/vat_summary_report.py` | satis/alis KDV ozeti | `tax_rate` normalize, `tax_amount` ve `total_amount` deterministic hesap |
| `reports/personnel_expense_report.py` | personel gider analizi | `employer_cost` sadece SGK/yuk, `total_employer_cost` ayri ve deterministic |
| `reports/sales_performance_report.py` | satis performansi | gross sales / refunds / net sales ayrimi, refund-aware leaderboard, `return_status` destegi |
| `reports/profitability_report.py` | nakit bazli karlilik | net cash profit mantigi, `accounting_profit=None`, gerekirse gross profit sadece COGS varsa |
| `reports/current_account_report.py` | cari hesap takip | acik borc, acik alacak, net acik pozisyon, paid satirlari aging disina alma |
| `reports/payroll_cost_report.py` | maas ve personel maliyeti | `sgk_employer` turetme, `total_employer_cost` tekrar hesaplama, toplam vergi/SGK alanlari |
| `reports/inventory_cost_report.py` | stok maliyet | `inventory_key`, weighted average, movement-summary tutarliligi, negative stock clamp |
| `reports/tax_calculation_report.py` | vergi hesaplama | vergi turu normalize, donem derive, tax amount deterministic hesap |

### `reports/personnel_expense_report.py`

Ana mantik:

- `gross_salary` zorunludur
- `employer_cost` bos ise `gross_salary * EMPLOYER_SGK_RATE`
- `total_employer_cost = gross_salary + employer_cost + bonus + benefits + employer_extra_cost`
- input `total_employer_cost` varsa compare edilir, fark varsa warning uretilir

Urettigi temel sheet'ler:

- departman ozeti
- personel detaylari
- aylik trend

### `reports/payroll_cost_report.py`

Ana mantik:

- `sgk_employer` bos ise brut maastan turetilir
- `total_employer_cost` her zaman deterministic tekrar hesaplanir
- `toplam_vergi = income_tax + stamp_tax`
- `toplam_sgk = sgk_employee + sgk_employer`

### `reports/sales_performance_report.py`

Bu rapor, son donemde en cok finansal semantik duzeltmesi alan raporlardan biridir.

Ana mantik:

- `transaction_type` varsa canonical normalize edilir
- yoksa default `sale`
- `return_status` varsa bilgi olarak tutulur
- `total_sales` mumkunse `quantity * unit_price - discount` ile yeniden hesaplanir
- refund satirlari net satisi dusurur
- KPI'lar gross/refund/net ayrimini acikca yazar

Temel KPI alanlari:

- `gross_sales`
- `refund_total`
- `net_sales`
- `gross_quantity`
- `refund_quantity`
- `net_quantity`
- `gross_order_count`
- `refund_order_count`
- `net_order_count`
- `net_average_order_value`
- `top_product_by_revenue`
- `top_product_by_quantity`
- `top_customer`
- `top_salesperson`

### `reports/inventory_cost_report.py`

Bu raporun ana tasarim karari:

```text
cost_method = weighted_average
```

Kritik mantiklar:

- `inventory_key = product_code if varsa else product_name`
- ayni `product_code` farkli `product_name` ile gelirse warning uretilir ama bolunmez
- `stock_in` degerlemesi input `unit_cost` ile yapilir
- `stock_out` degerlemesi weighted average ile yapilir
- negative stock varsa kalan stok negatif olabilir ama stok degeri negatife dusmez

Sheet'ler:

- `Stok Maliyet Ozeti`
- `Stok Hareketleri`
- `Kritik Stoklar`

### `reports/current_account_report.py`

Bu raporda eski "Acik Tutar" gibi muğlak kavramlar yerine acik yon ayrimi vardir:

- `Acik Borc`
- `Acik Alacak`
- `Net Acik Pozisyon`
- `Vadesi Gecmis Borc`
- `Vadesi Gecmis Alacak`

Paid satirlar aging disina cikarilir.

### `reports/debt_receivable_report.py`

Bu raporun son duzeltmeleri iki eksende onemlidir:

1. `counterparty_type` bazli risk mantigi
2. `Borc Tutari` / `Alacak Tutari` kolonlarindan `amount` ve `direction` turetme

Yani bu rapor artik amount/direction eksik diye hemen fail olmak yerine, `debt_amount` ve `receivable_amount` alanlarindan deterministic karar verebilir.

### `reports/profitability_report.py`

Bu rapor muhasebesel net kar raporu gibi davranmamasi icin "Nakit Bazli Karlilik" olarak netlestirildi.

Summary tarafinda:

- `cash_profit`
- `accounting_profit = None`
- `net_cash_profit_loss`
- gerekirse `gross_profit`

alanlari bulunur.

### `reports/vat_summary_report.py`

Bu rapor:

- `0.20 -> 20`
- `20 -> 20`

gibi oran normalizasyonunu yapar ve `tax_amount` ile `total_amount` alanlarini deterministic hesaplar.

### `reports/tax_calculation_report.py`

Bu rapor KDV ozetinden farkli olarak vergi turu ve donem uzerine kuruludur.

Ek davranislar:

- `tax_type` canonical mapping
- `period` eksikse tarihten derive etme
- pivot benzeri donemsel toplamlar

### Rapor template dosyalari

Her raporun `reports/<report_id>/template.json` dosyasi vardir. Bu dosyalar su bilgileri tasir:

- `report_id`
- `display_name`
- `description`
- `family`
- `supported_inputs`
- `input_contract`
- `output_kinds`
- `template_version`
- `handler_class`
- `alternative_reports`

Projede bulunan template dosyalari:

- `reports/income_expense_report/template.json`
- `reports/cash_flow_report/template.json`
- `reports/debt_receivable_report/template.json`
- `reports/vat_summary_report/template.json`
- `reports/personnel_expense_report/template.json`
- `reports/sales_performance_report/template.json`
- `reports/profitability_report/template.json`
- `reports/current_account_report/template.json`
- `reports/payroll_cost_report/template.json`
- `reports/inventory_cost_report/template.json`
- `reports/tax_calculation_report/template.json`

---

## 6.9 `report_handlers/` Klasoru

Bu klasor legacy rapor mimarisini tutar.

| Dosya | Rol |
|---|---|
| `report_handlers/base_report_handler.py` | eski handler soyut tabani |
| `report_handlers/income_expense_handler.py` | gelir-gider raporu hesaplari |
| `report_handlers/cash_flow_handler.py` | nakit akis raporu hesaplari |
| `report_handlers/debt_receivable_handler.py` | eski borc-alacak hesap mantigi |
| `report_handlers/__init__.py` | package marker |

### Neden hala duruyor?

Cunku:

- `income_expense_report` ve `cash_flow_report` hala bu akisi kullaniyor
- bu katmanda chart ve metric mantigi oturmus durumda
- structured_financial raporlara gecis tamamlanmis olsa da legacy kod halen calisir durumda tutuluyor

Not:

- `report_handlers/debt_receivable_handler.py` artik ana debt receivable raporunun aktif yolu degildir
- aktif debt receivable raporu `reports/debt_receivable_report.py` dosyasindadir

---

## 6.10 `tests/` Klasoru

| Dosya | Rol |
|---|---|
| `tests/test_mvp_pipeline.py` | tum ana regression ve entegrasyon testleri |

Bu test dosyasi bugun sistemin davranis sozlesmesidir. Yani yalnizca "kod calisiyor mu" degil, "finansal anlam dogru mu" sorusunu da kontrol eder.

Ornek test gruplari:

- registry tum raporlari yukleyebiliyor mu
- personel gideri `employer_cost` ile `total_employer_cost` ayri mi
- payroll `sgk_employer` turetiyor mu
- KDV oran normalizasyonu calisiyor mu
- invalid tax rate warning veriyor mu
- satis raporu refund'i dogru dusuyor mu
- `return_status` yanlis map edilse bile otomatik duzeltiliyor mu
- inventory movement ile summary ayni valuation mantigini kullaniyor mu
- mixed currency warning uretiliyor mu
- masking export'ta warning uretiyor mu
- borc-alacak raporu split borc/alacak kolonlarindan amount/direction turetiyor mu

---

## 6.11 `scripts/` Klasoru

| Dosya | Rol |
|---|---|
| `scripts/generate_sample_reports.py` | ornek transaction verisiyle hizli rapor uretim denemesi |

Bu script daha cok:

- manuel smoke test
- demo
- baseline output gorme

icin faydalidir.

---

## 7. Rapor Bazli Son Gelistirmelerin Ozet Listesi

Bu bolum, yonetici ozeti gibi okunabilir.

### Gelir-Gider Raporu

- legacy warning string'leri structured warning formatina uyumlu hale getirildi
- output asamasinda string warning kaynakli crash engellendi

### Nakit Akis Raporu

- legacy mimaride kalsa da yeni output/warning contract'i ile uyumlu hale getirildi

### Borc-Alacak Raporu

- `counterparty_type` bazli risk skoru eklendi
- `debt_amount` / `receivable_amount` kolonlarindan `amount` ve `direction` turetilir hale geldi
- amount/direction eksik diye tum satirlarin dusmesi engellendi

### KDV Ozet Raporu

- `tax_rate` normalize edilir oldu
- `tax_amount` ve `total_amount` yeniden hesaplanir oldu
- mismatch warning'leri eklendi

### Personel Gider Analiz Raporu

- `employer_cost` sadece SGK/isveren yuk olarak anlamlandirildi
- `total_employer_cost` ayri alan olarak hesaplanir oldu
- mapping tarafinda `SGK Isveren Payi` ile `Isveren Toplam Maliyeti` ayrildi

### Satis Performans Raporu

- `gross_sales`, `refund_total`, `net_sales` semantigi netlestirildi
- refund ve return davranisi standartlastirildi
- `return_status` alani eklendi
- `transaction_type` yoksa default `sale` kabul ediliyor
- `Iade Durumu` kolonu yanlislikla `transaction_type` map edilirse runtime'da duzeltiliyor

### Nakit Bazli Karlilik Raporu

- isimlendirme netlestirildi
- `cash_profit` ve `accounting_profit` ayrimi gelecege hazir hale getirildi

### Cari Hesap Takip Raporu

- paid satirlar open/aging hesaplarindan cikarildi
- acik borc/acik alacak/net acik pozisyon alanlari net ayrildi

### Maas ve Personel Maliyet Raporu

- `total_employer_cost` her zaman deterministic hesaplanir oldu
- `toplam_vergi` ve `toplam_sgk` deterministic hale geldi

### Stok Maliyet Raporu

- `weighted_average` maliyet yontemi netlestirildi
- `inventory_key` standardi kuruldu
- stock-in ve stock-out movement valuation kurallari ayrildi
- negative stock'ta stok degeri negatife dusmez hale getirildi
- summary ile movement sheet ayni valuation map'i kullanir hale geldi

### Vergi Hesaplama Raporu

- `tax_rate` normalize edilir oldu
- `tax_amount` deterministic hale geldi
- `period` tarihten derive edilmeye devam ediyor

---

## 8. Aktif Veri Sozlesmeleri ve Warning Sozlesmesi

### 8.1 Mapping JSON sozlesmesi

Mapping JSON genel olarak su tipleri kullanir:

- `column`
- `derived`
- `constant`
- `not_available`
- `llm_infer_later`

Derived rule tipleri:

- `boolean_columns`
- `debit_credit_amount`
- `debit_credit_direction`
- `signed_amount_direction`

### 8.2 Warning object sozlesmesi

Standart warning alanlari:

```json
{
  "type": "mismatch",
  "severity": "warning",
  "message": "Aciklama",
  "row": 12,
  "field": "tax_amount",
  "input_value": 1500,
  "calculated_value": 2000,
  "action": "used_calculated_value",
  "audit_run_id": "...",
  "calculated_from": ["base_amount", "tax_rate"],
  "lineage": {
    "rule": "base_amount * tax_rate / 100",
    "source_fields": ["base_amount", "tax_rate"],
    "config_snapshot": {}
  }
}
```

Severity mantigi:

- `info`
- `warning`
- `critical`
- `blocking`

### 8.3 Execution status mantigi

- `blocking` varsa `failed`
- `critical` varsa `warning`
- sadece `info/warning` varsa `success`
- sheet bazli kismi hata olursa `partial`

---

## 9. Bu Projeye Yeni Bir Rapor Nasil Eklenir?

Genel yol su sekildedir:

1. `reports/<new_report>/template.json` olustur
2. `reports/index.json` icine kaydet
3. Yeni rapor structured_financial olacaksa `reports/<new_report>.py` icinde `ReportAgent(BaseReportAgent)` yaz
4. `required_fields`, `optional_fields`, `numeric_fields`, `date_fields` tanimla
5. `validate()` icinde deterministic validation kurallarini yaz
6. `generate()` icinde summary, tables, sheets sozlesmesini dondur
7. gerekirse `utils/mapping_utils.py` alias'larini genislet
8. `tests/test_mvp_pipeline.py` icine regression ekle

Eger legacy chart agirlikli bir rapor olacaksa:

1. `report_handlers/*.py` icine handler ekle
2. template'de `handler_class` olarak onu goster
3. `family="transaction"` mantigina uygun normalize alanlari kullan

Pratik olarak yeni gelistirmeler icin tavsiye edilen yol structured_financial mimaridir.

---

## 10. Bilinmesi Gereken Sinirlar ve Tasarim Notlari

1. Projede iki nesil mimari birlikte durdugu icin yeni gelen bir gelistirici ilk basta karmaşa yasayabilir.
2. `AIAnalysisService` mevcut ama her raporun zorunlu parcasi degildir.
3. `output_generator.py` icinde PNG helper'i vardir, ancak top-level akista JSON/XLSX kadar merkezi degildir.
4. Bazi eski dosyalarda console encoding nedeniyle Turkce karakterler bozuk gorunebilir; alias normalization katmani bunu yumusatmaya calisir.
5. Mixed-currency durumunda sistem conversion yapmak yerine warning uretmeyi tercih eder.
6. Hedef, kullanici verisini "dogru kabul etmek" degil, "dogrulanabilir advisory input" olarak ele almaktir.

---

## 11. Bu Projede En Hizli Oryantasyon Rotasi

Projeyi yeni devralan bir gelistirici icin en verimli okuma sirası:

1. `main.py`
2. `config.py`
3. `services/report_registry_service.py`
4. `services/report_execution_service.py`
5. `reports/base_agent.py`
6. `utils/mapping_utils.py`
7. `utils/validation.py`
8. `utils/money_utils.py`
9. `utils/warning_utils.py`
10. ilgilenilen spesifik rapor dosyasi
11. `tests/test_mvp_pipeline.py`

Bu sira takip edilirse hem genel mimari, hem warning/mapping/validation engine'i, hem de rapor-ozel is kurallari hizli sekilde kavranir.

---

## 12. Sonuc

Bu proje bugun yalnizca Excel'den tablo ceken basit bir script degildir. Artik:

- deterministic
- Decimal-safe
- audit-friendly
- explainable
- warning-aware
- timezone-safe
- mixed-currency-aware
- ERP/muhasebe mantigina daha yakin

bir finansal raporlama cekirdegi haline gelmistir.

En onemli tasarim ilkesi tekrar vurgulanmalidir:

```text
LLM hesaplama yapmaz.
Kritik finansal alanlar Python tarafinda deterministic hesaplanir.
Kullanici inputu advisory kabul edilir.
Override, derive ve row drop islemleri warning ile explain edilir.
```

Bu prensipler, projeyi hem guvenilir hem de genisletilebilir hale getiren ana omurgadir.
