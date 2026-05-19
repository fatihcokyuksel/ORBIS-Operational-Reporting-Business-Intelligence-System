from __future__ import annotations


DISCLAIMER_TITLE = "Yapay Zeka Kullanım Uyarısı"
DISCLAIMER_TEXT = (
    "Bu rapor yapay zeka destekli olarak oluşturulmuştur. Finansal kararlar verilmeden önce "
    "rapordaki tüm hesaplamalar, çıkarımlar ve öneriler tekrar kontrol edilmelidir. Sonuçlar "
    "eksiklik veya hata içerebilir; insan doğrulaması zorunludur."
)
BRANDING_TEXT = "ORBIS tarafından oluşturuldu"

SHEET_NAMES = {
    "main": "Rapor",
    "charts": "Grafikler",
    "data": "Normalize Veri",
    "summary": "Metodoloji ve Ek Bilgi",
}

TEXT = {
    "created_at": "Oluşturma zamanı",
    "source_file": "Kaynak dosya",
    "main_summary": "Ana Finansal Özet",
    "metrics": "Metrikler",
    "metric": "Metrik",
    "value": "Değer",
    "type": "Tür",
    "ai_analysis": "Yapay Zeka Analizi",
    "charts": "Görsel Analitik",
    "normalized_data": "Normalize İşlem Verisi",
    "compact_summary": "Metodoloji ve Ek Bilgi",
    "no_data": "Veri yok",
}

FIELD_LABELS = {
    "date": "Tarih",
    "description": "Açıklama",
    "amount": "Tutar",
    "direction": "Yön",
    "balance": "Bakiye",
    "counterparty": "Karşı Taraf",
    "category": "Kategori",
    "currency": "Para Birimi",
    "source": "Kaynak",
}

METRIC_TYPE_LABELS = {
    "currency": "Tutar",
    "percentage": "Oran",
    "count": "Adet",
    "text": "Metin",
    "date": "Tarih",
}

DIRECTION_LABELS = {
    "income": "Gelir",
    "inflow": "Giriş",
    "expense": "Gider",
    "outflow": "Çıkış",
    "debt": "Borç",
    "receivable": "Alacak",
    "calculated": "Hesaplanan",
    "deductible": "İndirilecek",
}

SOURCE_LABELS = {
    "excel": "Excel",
    "prompt": "Kullanıcı metni",
}

TURKISH_LABELS = {
    # Summary & metrics
    "total_income": "Toplam Gelir",
    "total_expense": "Toplam Gider",
    "net_profit": "Net Kar",
    "net_result": "Net Sonuç",
    "net_income": "Net Gelir",
    "cash_in": "Nakit Girişi",
    "cash_out": "Nakit Çıkışı",
    "net_cash_flow": "Net Nakit Akışı",
    "profit_margin": "Kar Marjı",
    "warning_count": "Uyarı Sayısı",
    "dropped_row_count": "Atılan Satır Sayısı",
    "recalculated_field_count": "Yeniden Hesaplanan Alan Sayısı",
    "reporting_currency": "Raporlama Para Birimi",
    
    # Sales
    "total_sales": "Toplam Satış",
    "gross_sales": "Brüt Satış",
    "refund_total": "Toplam İade",
    "net_sales": "Net Satış",
    "gross_quantity": "Toplam Adet",
    "refund_quantity": "Toplam İade Adedi",
    "net_quantity": "Net Adet",
    "gross_order_count": "Toplam Sipariş",
    "refund_order_count": "Toplam İade İşlemi",
    "net_order_count": "Net Sipariş Sayısı",
    "net_average_order_value": "Net Ortalama Sipariş Değeri",
    "top_product_by_revenue": "En Çok Satan Ürün (Ciro)",
    "top_product_by_quantity": "En Çok Satan Ürün (Adet)",
    "top_customer": "En Büyük Müşteri",
    "top_salesperson": "En Başarılı Satış Temsilcisi",
    "total_quantity": "Toplam Adet",
    "total_refund": "Toplam İade",
    "refund_count": "İade Sayısı",
    
    # Personnel & payroll
    "total_employer_cost": "Toplam İşveren Maliyeti",
    "gross_salary": "Brüt Maaş",
    "benefits": "Yan Haklar",
    "net_salary": "Net Maaş",
    "sgk_employee": "SGK İşçi Payı",
    "sgk_employer": "SGK İşveren Payı",
    "income_tax": "Gelir Vergisi",
    "stamp_tax": "Damga Vergisi",
    
    # Inventory
    "inventory_value": "Stok Değeri",
    "warehouse": "Depo",
    "quantity": "Miktar",
    "unit_cost": "Birim Maliyet",
    
    # Debt/receivable & current account
    "due_date": "Vade Tarihi",
    "overdue": "Geciken",
    "aging": "Yaşlandırma",
    "open_positions": "Açık Pozisyonlar",
    "delayed_positions": "Gecikmiş Pozisyonlar",
    "debt": "Borç",
    "receivable": "Alacak",
    
    # Taxes & VAT
    "tax_rate": "Vergi Oranı",
    "tax_amount": "Vergi Tutarı",
    "base_amount": "Matrah",
    "tax_type": "Vergi Türü",
    "calculated_vat": "Hesaplanan KDV",
    "deductible_vat": "İndirilecek KDV",
    "net_vat": "Net KDV",
    "total_tax_amount": "Toplam Vergi Tutarı",
    
    # Metadata
    "currencies_detected": "Tespit Edilen Para Birimleri",
    "totals_by_currency": "Para Birimine Göre Toplamlar",
    
    # General columns
    "date": "Tarih",
    "description": "Açıklama",
    "amount": "Tutar",
    "direction": "Yön",
    "balance": "Bakiye",
    "counterparty": "Karşı Taraf",
    "category": "Kategori",
    "currency": "Para Birimi",
    "source": "Kaynak",
    "income": "Gelir",
    "expense": "Gider",
    "inflow": "Giriş",
    "outflow": "Çıkış",
    "customer": "Müşteri",
    "product_name": "Ürün Adı",
    "transaction_type": "İşlem Türü",
    "transaction_direction": "İşlem Yönü",
}

def prettify_label(value: str) -> str:
    cleaned = str(value).lower().replace(" ", "_").strip()
    if cleaned in TURKISH_LABELS:
        return TURKISH_LABELS[cleaned]
    return str(value).replace("_", " ").strip().title()
