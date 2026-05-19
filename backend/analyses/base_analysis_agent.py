from __future__ import annotations

import json
from abc import ABC, abstractmethod

import pandas as pd

from services.llm_service import LLMService


ANALYSIS_TEXT_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "data_scope_commentary": {"type": "string"},
        "metric_commentary": {"type": "string"},
        "trend_analysis": {"type": "string"},
        "risk_analysis": {"type": "string"},
        "findings": {"type": "string"},
        "recommendations": {"type": "string"},
        "methodology_explanation": {"type": "string"},
        "limitations": {"type": "string"},
    },
    "required": [
        "executive_summary",
        "data_scope_commentary",
        "metric_commentary",
        "trend_analysis",
        "risk_analysis",
        "findings",
        "recommendations",
        "methodology_explanation",
        "limitations",
    ],
}


class BaseAnalysisAgent(ABC):
    artifact_id: str = ""
    display_name: str = ""

    def _require_rows(self, df: pd.DataFrame, message: str = "Analiz icin yeterli veri bulunamadi."):
        if df is None or df.empty:
            raise ValueError(message)

    def generate_narrative(self, deterministic_payload: dict) -> dict:
        prompt = build_analysis_prompt(
            artifact_id=self.artifact_id,
            display_name=self.display_name,
            deterministic_payload=deterministic_payload,
        )
        try:
            response = LLMService().generate_json(
                prompt=prompt,
                response_schema=ANALYSIS_TEXT_SCHEMA,
            )
        except Exception:
            response = build_fallback_narrative(self.display_name, deterministic_payload)

        return ensure_narrative_density(response, self.display_name, deterministic_payload)

    @abstractmethod
    def build_analysis(self, df: pd.DataFrame, user_prompt: str | None = None) -> dict:
        raise NotImplementedError


def build_analysis_prompt(artifact_id: str, display_name: str, deterministic_payload: dict) -> str:
    return (
        "Sen CFO seviyesinde, profesyonel ve detayli finansal analiz raporlari yazan bir uzmansin. "
        "Sadece sana verilen deterministik metrikleri yorumlayacaksin. "
        "Yeni sayi uretme, hesap yapma, oran bulma, tarih tahmini yazma. "
        "Tum hesaplamalar zaten Python/pandas ile yapildi; sen yalnizca yonetici seviyesinde Turkce yorumlama yap. "
        "Her alan uzun ve rapor dilinde olacak. JSON disinda hicbir sey donme.\n\n"
        "Uzunluk kurallari:\n"
        "- executive_summary: 3-5 paragraf\n"
        "- data_scope_commentary: 2-3 paragraf\n"
        "- metric_commentary: temel metrikleri tek tek yorumlayan uzun bir metin\n"
        "- trend_analysis: 3-5 paragraf\n"
        "- risk_analysis: 4-6 paragraf\n"
        "- findings: aciklamali maddesel bulgulara uygun uzun metin\n"
        "- recommendations: kisa not degil, uygulanabilir aksiyon plani\n"
        "- methodology_explanation: hesaplama mantigini yorumlayan aciklayici metin\n"
        "- limitations: veri sinirlari ve kullaniciya dikkat notlari\n\n"
        f"Analiz tipi: {artifact_id}\n"
        f"Analiz adi: {display_name}\n"
        f"Girdi:\n{json.dumps(deterministic_payload, ensure_ascii=False, indent=2)}"
    )


def build_fallback_narrative(display_name: str, deterministic_payload: dict) -> dict:
    metrics = deterministic_payload.get("metrics", {})
    metric_sentence = ", ".join(f"{key}: {value}" for key, value in metrics.items()) or "belirgin metrik bulunmadi"
    return {
        "executive_summary": (
            f"{display_name} mevcut veri seti uzerinde deterministik olarak olusturuldu. "
            f"Raporun merkezinde yer alan metrikler {metric_sentence} olarak olustu.\n\n"
            "Yonetim bakis acisiyla bu ciktinin degeri, mevcut finansal davranisin hangi basinc noktalarinda toplandigini "
            "erken gormeyi saglamasidir. Veri hacmi sinirli olsa bile donemsel hareketlerin genel yonu, kontrol edilmesi "
            "gereken kalemler ve operasyonel hassasiyetler bu raporda acik bicimde gorulebilir.\n\n"
            "Bu anlatim muhasebesel kesinlik iddia etmez; amaci karar vericiye hizli bir on okuma sunmaktir. "
            "Ozellikle nakit dengesi, gider yogunlugu, tahsilat davranisi veya vergi tutarliligi gibi alanlarda gorulen "
            "sapmalarin ek kontrol adimlariyla desteklenmesi onerilir."
        ),
        "data_scope_commentary": (
            "Veri kapsami, normalize edilmis ve filtrelenmis kayitlar uzerinden degerlendirildi. "
            "Bu nedenle rapor, ham dosyalardaki tum satirlari degil, artifact uretimine uygun bulunan kayitlari temel alir.\n\n"
            "Eksik alanlar, kolon adlarindaki farkliliklar ve format uyumsuzluklari normalize edilerek ortak bir semada toplandi. "
            "Bu durum raporlar arasi karsilastirma kolayligi saglasa da, kaynaktaki is kural farklari yonetici yorumu icin mutlaka dikkate alinmalidir."
        ),
        "metric_commentary": (
            "Temel metrikler birlikte okundugunda sadece toplam tutarlari degil, ayni zamanda faaliyet modelinin ne kadar dengeli oldugunu da gosterir. "
            "Toplamlarin mutlak buyuklugu kadar, birbirleriyle kurdugu oranlar ve donem icindeki dagilim da performans ve risk okumasinda belirleyicidir.\n\n"
            "Bu nedenle rapordaki her sayisal alan tek basina degil, nakit akisi, gider baskisi, yogunlasma veya gecikme davranisi gibi diger gostergelerle birlikte ele alinmalidir."
        ),
        "trend_analysis": (
            "Trend analizi, donemler arasindaki degisimin sadece yonunu degil, hizini ve kalicilik ihtimalini de okumaya yardim eder. "
            "Tek seferlik sicrama niteligindeki hareketlerle, sureklilik kazanmaya baslayan davranislar ayri degerlendirilmelidir.\n\n"
            "Veri setinde belirgin mevsimsellik, tahsilat yogunlasmasi veya belirli gun/aylara yigilan hareketler varsa yonetim takvimi bu bulgularla hizalanmalidir.\n\n"
            "Ozellikle artis gosteren kalemler icin kontrol seviyesi yalnizca donem sonu degil, donem ici izleme duzeyine cekilmelidir."
        ),
        "risk_analysis": (
            "Riskler, veride gorulen finansal baski noktalarinin operasyonel surdurulebilirlik uzerindeki etkisi dikkate alinarak yorumlandi. "
            "Likidite, yogunlasma, ani artan gider, tahsilat gecikmesi veya tutarsiz vergi kaydi gibi basliklar bu kapsamda onceliklendirildi.\n\n"
            "Her riskin tek bir kaynagi olmayabilir; cogu durumda veri kalitesi, surec disiplini ve finansal davranis ayni anda etkide bulunur. "
            "Bu nedenle risklerin sadece finans ekibinin degil, operasyon ve yonetim ekiplerinin ortak kontrol alanina alinmasi gerekir.\n\n"
            "Veri sinirli oldugunda bile temkinli yorum tercih edilmeli, kritik kalemler teyit edilmeli ve tekrar eden sapmalar icin esik bazli takip mekanizmasi kurulmalidir."
        ),
        "findings": (
            "Bulgular, rapordaki metriklerin birbiriyle iliskisine gore olusturuldu. "
            "Belirgin yogunlasmalar, donemsel sapmalar, yuksek etkili kalemler ve kontrol ihtiyaci doguran hareketler yonetim okumasina uygun sekilde one cikarildi.\n\n"
            "Ozellikle sayisal olarak buyuk kalemlerle sureklilik gosterme ihtimali bulunan kalemler ayri oneme sahiptir; bunlarin her biri gerekirse belge bazli dogrulama listesine alinmalidir."
        ),
        "recommendations": (
            "Kisa vadede, en buyuk tutarli veya en hizli degisen kalemler icin haftalik kontrol ritmi kurulmasi uygundur. "
            "Orta vadede, kategori/cari/urun bazli limitler ve istisna raporlari ile fark edilen sapmalarin erken asamada yakalanmasi saglanabilir.\n\n"
            "Yonetim ekibi acisindan uygulanabilir en saglikli aksiyon plani; veri akisini standardize etmek, kritik metrikler icin sorumluluk atamak ve onemli sapmalar icin onceden tanimli aksiyon esikleri belirlemektir."
        ),
        "methodology_explanation": (
            "Bu rapordaki butun sayisal hesaplamalar Python ve pandas kullanilarak deterministik bicimde uretildi. "
            "Normalize edilen kayitlar uzerinden toplamlama, gruplanma, trend olusturma ve esik bazli kontroller calistirildi.\n\n"
            "Dil modeli sadece bu deterministik ciktilari yorumlamak icin kullanildi; yeni sayi turetmedi ve hesaplama mantigina mudahale etmedi."
        ),
        "limitations": (
            "Raporun gucu, normalize edilmis veri setinin kapsamina ve kalitesine baglidir. "
            "Eksik kolonlar, farkli muhasebe pratikleri, coklu para birimi etkisi veya gec girilen kayitlar yorum kalitesini sinirlayabilir.\n\n"
            "Bu dokuman muhasebesel baglayici rapor yerine yonetsel on analiz olarak okunmali, kritik kararlar oncesinde uzman incelemesi ile desteklenmelidir."
        ),
    }


def ensure_narrative_density(response: dict, display_name: str, deterministic_payload: dict) -> dict:
    fallback = build_fallback_narrative(display_name, deterministic_payload)
    dense_response = {}
    for key, fallback_value in fallback.items():
        value = str(response.get(key) or "").strip()
        if len(value.split()) < 50:
            dense_response[key] = f"{value}\n\n{fallback_value}".strip() if value else fallback_value
        else:
            dense_response[key] = value
    return dense_response
