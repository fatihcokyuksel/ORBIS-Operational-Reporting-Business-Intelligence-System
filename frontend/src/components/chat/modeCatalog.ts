'use client'

import {
  BarChart3,
  FileSpreadsheet,
  FileText,
  Landmark,
  LineChart,
  PieChart,
  ShieldAlert,
  TrendingUp,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export type ArtifactType = 'report' | 'chart' | 'analysis'

export interface ArtifactInputRequirement {
  artifactType: ArtifactType
  label: string
  outputFormat: 'xlsx' | 'jpg' | 'pdf'
  description: string
  requiredColumns: string[]
  optionalColumns: string[]
  examples: string[]
  supportsPromptOnly?: boolean
}

export interface ModeItem {
  id: string
  label: string
  icon: LucideIcon
}

export interface ModeGroup {
  id: ArtifactType
  label: string
  icon: LucideIcon
  items: ModeItem[]
}

export const MAX_ARTIFACT_FILES = 5
export const MAX_ARTIFACT_FILE_SIZE_MB = 10

export const ARTIFACT_INPUT_REQUIREMENTS: Record<string, ArtifactInputRequirement> = {
  income_expense_report: {
    artifactType: 'report',
    label: 'Gelir Gider Raporu',
    outputFormat: 'xlsx',
    description: 'Gelir ve gider hareketlerini iceren Excel dosyalari yukleyin. Birden fazla .xlsx dosyasi kabul edilir.',
    requiredColumns: ['Tarih', 'Tutar', 'Gelir/Gider yonu', 'Aciklama'],
    optionalColumns: ['Kategori', 'Cari/Firma', 'Bakiye', 'Para birimi'],
    examples: ['Ayrik gelir ve gider dosyalari birlikte yuklenebilir.'],
  },
  cash_flow_report: {
    artifactType: 'report',
    label: 'Nakit Akis Raporu',
    outputFormat: 'xlsx',
    description: 'Nakit giris ve cikislarini iceren .xlsx dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Tutar', 'Nakit giris/cikis yonu'],
    optionalColumns: ['Aciklama', 'Kategori', 'Bakiye'],
    examples: ['Aylik kasa/banka hareketleri tek dosyada veya donemsel parcalarda olabilir.'],
  },
  debt_receivable_report: {
    artifactType: 'report',
    label: 'Borc-Alacak Raporu',
    outputFormat: 'xlsx',
    description: 'Borc ve alacak hareketleri icin cari bazli .xlsx dosyalari yukleyin.',
    requiredColumns: ['Islem Tarihi', 'Cari/Firma', 'Borc veya Alacak Tutari'],
    optionalColumns: ['Vade Tarihi', 'Odeme Durumu', 'Fatura No', 'Aciklama'],
    examples: ['Ayni carinin farkli donem dosyalari birlestirilebilir.'],
  },
  vat_summary_report: {
    artifactType: 'report',
    label: 'KDV Ozet Raporu',
    outputFormat: 'xlsx',
    description: 'KDV kayitlarini iceren .xlsx dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Matrah', 'KDV orani', 'KDV tutari'],
    optionalColumns: ['Fatura No', 'Cari/Firma', 'Islem tipi', 'Toplam tutar'],
    examples: ['Satis ve alis KDV kayitlari farkli dosyalarda olabilir.'],
  },
  personnel_expense_report: {
    artifactType: 'report',
    label: 'Personel Gider Analiz Raporu',
    outputFormat: 'xlsx',
    description: 'Personel odeme ve yan hak verilerini iceren .xlsx dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Personel adi', 'Brut maas'],
    optionalColumns: ['Departman', 'Prim', 'Yan haklar', 'Toplam isveren maliyeti'],
    examples: ['Bordro ve yan hak dosyalari birlikte islenebilir.'],
  },
  sales_performance_report: {
    artifactType: 'report',
    label: 'Satis Performans Raporu',
    outputFormat: 'xlsx',
    description: 'Satis hareketlerini iceren .xlsx dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Musteri', 'Urun/Hizmet', 'Toplam satis'],
    optionalColumns: ['Miktar', 'Satis temsilcisi', 'Bolge', 'Iade durumu'],
    examples: ['Farkli sube veya donem dosyalari tek raporda birlestirilebilir.'],
  },
  profitability_report: {
    artifactType: 'report',
    label: 'Karlilik Raporu',
    outputFormat: 'xlsx',
    description: 'Gelir ve gider hereketlerini iceren .xlsx dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Tutar', 'Gelir/Gider yonu'],
    optionalColumns: ['Kategori', 'Aciklama', 'Para birimi'],
    examples: ['Gelir dosyasi ve gider dosyasi ayrik olabilir.'],
  },
  current_account_report: {
    artifactType: 'report',
    label: 'Cari Hesap Takip Raporu',
    outputFormat: 'xlsx',
    description: 'Cari borc/alacak takibi icin .xlsx dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Cari/Firma', 'Borc/Alacak yonu', 'Tutar'],
    optionalColumns: ['Vade Tarihi', 'Odeme Durumu', 'Aciklama'],
    examples: ['Tahsilat ve odeme hareketleri ayrik dosyalarda olabilir.'],
  },
  payroll_cost_report: {
    artifactType: 'report',
    label: 'Maas ve Personel Maliyet Raporu',
    outputFormat: 'xlsx',
    description: 'Bordro maliyetlerini iceren .xlsx dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Personel adi', 'Brut maas'],
    optionalColumns: ['Net maas', 'Gelir vergisi', 'SGK', 'Toplam isveren maliyeti'],
    examples: ['Farkli ay bordrolari tek raporda birlestirilebilir.'],
  },
  inventory_cost_report: {
    artifactType: 'report',
    label: 'Stok Maliyet Raporu',
    outputFormat: 'xlsx',
    description: 'Stok miktar ve maliyet verilerini iceren .xlsx dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Urun adi', 'Miktar', 'Birim maliyet'],
    optionalColumns: ['Urun kodu', 'Depo', 'Tedarikci', 'Kategori'],
    examples: ['Giris ve cikis hareketleri farkli dosyalarda olabilir.'],
  },
  tax_calculation_report: {
    artifactType: 'report',
    label: 'Vergi Hesaplama Raporu',
    outputFormat: 'xlsx',
    description: 'Vergi hesap verilerini iceren .xlsx dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Vergi turu', 'Matrah', 'Vergi tutari'],
    optionalColumns: ['Vergi orani', 'Islem tipi', 'Cari/Firma'],
    examples: ['Birden fazla beyan donemi tek raporda birlestirilebilir.'],
  },

  income_expense_pie_chart: {
    artifactType: 'chart',
    label: 'Gelir-Gider Pasta Grafigi',
    outputFormat: 'jpg',
    description: 'Gelir ve gider toplamlari iceren Excel dosyalari yukleyin veya veriyi dogrudan prompt ile yazin.',
    requiredColumns: ['Gelir/Gider yonu', 'Tutar'],
    optionalColumns: ['Tarih', 'Kategori', 'Para birimi'],
    examples: ['Ocak gelir 1 milyon TL, gider 650 bin TL.'],
    supportsPromptOnly: true,
  },
  monthly_expense_trend_chart: {
    artifactType: 'chart',
    label: 'Aylik Harcama Trend Grafigi',
    outputFormat: 'jpg',
    description: 'Gider tarih ve tutarlarini iceren Excel dosyalari yukleyin; isterseniz filtreyi prompt ile belirtin.',
    requiredColumns: ['Tarih', 'Gider tutari', 'Gider yonu'],
    optionalColumns: ['Kategori', 'Aciklama'],
    examples: ['Son 3 ay ve 50 bin uzeri islemler'],
    supportsPromptOnly: true,
  },
  cashflow_bar_chart: {
    artifactType: 'chart',
    label: 'Nakit Akis Bar Grafigi',
    outputFormat: 'jpg',
    description: 'Nakit giris/cikislarini iceren .xlsx dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Tutar', 'Gelir/Gider yonu'],
    optionalColumns: ['Aciklama', 'Kategori', 'Bakiye'],
    examples: ['Aylik nakit giris/cikis grafigi'],
    supportsPromptOnly: true,
  },
  top_expenses_chart: {
    artifactType: 'chart',
    label: 'En Buyuk Giderler Grafigi',
    outputFormat: 'jpg',
    description: 'En buyuk giderleri gormek icin gider verilerini iceren .xlsx dosyalari yukleyin.',
    requiredColumns: ['Aciklama veya kategori', 'Gider tutari'],
    optionalColumns: ['Tarih', 'Cari/Firma'],
    examples: ['Sadece 50 bin uzeri giderleri goster'],
  },
  daily_balance_change_chart: {
    artifactType: 'chart',
    label: 'Gunluk Bakiye Degisim Grafigi',
    outputFormat: 'jpg',
    description: 'Bakiye veya yonlu islem verisi iceren .xlsx dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Bakiye veya islem tutari'],
    optionalColumns: ['Gelir/Gider yonu', 'Hesap adi'],
    examples: ['Gunluk bakiye trendi'],
  },
  debt_receivable_distribution_chart: {
    artifactType: 'chart',
    label: 'Borc-Alacak Dagilim Grafigi',
    outputFormat: 'jpg',
    description: 'Cari bazli borc ve alacak bilgilerini iceren .xlsx dosyalari yukleyin.',
    requiredColumns: ['Cari/Firma', 'Borc veya alacak tutari'],
    optionalColumns: ['Vade tarihi', 'Odeme durumu'],
    examples: ['Cari bazli grouped bar chart'],
  },
  sales_performance_chart: {
    artifactType: 'chart',
    label: 'Satis Performans Grafigi',
    outputFormat: 'jpg',
    description: 'Urun veya musteri bazli satis verilerini iceren .xlsx dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Musteri veya urun', 'Toplam satis'],
    optionalColumns: ['Bolge', 'Satis temsilcisi', 'Miktar'],
    examples: ['Sadece Istanbul bolgesi satislari'],
  },
  tax_distribution_chart: {
    artifactType: 'chart',
    label: 'Vergi Dagilim Grafigi',
    outputFormat: 'jpg',
    description: 'Vergi turu veya oran dagilimlarini iceren .xlsx dosyalari yukleyin.',
    requiredColumns: ['Vergi turu veya orani', 'Vergi tutari'],
    optionalColumns: ['Tarih', 'Matrah'],
    examples: ['KDV oranina gore dagilim'],
  },

  financial_risk_analysis: {
    artifactType: 'analysis',
    label: 'Finansal Risk Analizi',
    outputFormat: 'pdf',
    description: 'Gelir ve gider hareketlerini iceren Excel dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Tutar', 'Gelir/Gider yonu', 'Aciklama'],
    optionalColumns: ['Kategori', 'Bakiye', 'Cari/Firma'],
    examples: ['Gelir-gider agirlikli genel finans verisi'],
  },
  cash_runway_analysis: {
    artifactType: 'analysis',
    label: 'Nakit Tukenme Riski Analizi',
    outputFormat: 'pdf',
    description: 'Nakit cikislari ve bakiye bilgisini iceren Excel dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Tutar', 'Gelir/Gider yonu'],
    optionalColumns: ['Bakiye', 'Aciklama', 'Kategori'],
    examples: ['Mevcut bakiye + harcama akisi'],
  },
  anomaly_spending_analysis: {
    artifactType: 'analysis',
    label: 'Anormal Harcama Analizi',
    outputFormat: 'pdf',
    description: 'Gider hareketlerini iceren Excel dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Tutar', 'Aciklama'],
    optionalColumns: ['Kategori', 'Cari/Firma'],
    examples: ['Yuksek ve siradisi giderlerin analizi'],
  },
  expense_optimization_analysis: {
    artifactType: 'analysis',
    label: 'Gider Optimizasyon Analizi',
    outputFormat: 'pdf',
    description: 'Gider kategorilerini iceren Excel dosyalari yukleyin.',
    requiredColumns: ['Gider tutari', 'Kategori', 'Aciklama'],
    optionalColumns: ['Tarih', 'Cari/Firma', 'Tekrarlayan odeme bilgisi'],
    examples: ['Abonelik ve duzenli gider analizi'],
  },
  profitability_analysis: {
    artifactType: 'analysis',
    label: 'Karlilik Analizi',
    outputFormat: 'pdf',
    description: 'Gelir ve gider hareketlerini iceren Excel dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Tutar', 'Gelir/Gider yonu'],
    optionalColumns: ['Kategori', 'Aciklama'],
    examples: ['Aylik kar/zarar davranisi'],
  },
  receivable_debt_risk_analysis: {
    artifactType: 'analysis',
    label: 'Borc-Alacak Risk Analizi',
    outputFormat: 'pdf',
    description: 'Cari bazli borc ve alacak hareketlerini iceren Excel dosyalari yukleyin.',
    requiredColumns: ['Cari/Firma', 'Borc veya alacak tutari', 'Vade tarihi'],
    optionalColumns: ['Odeme durumu', 'Tarih', 'Fatura No'],
    examples: ['Riskli cariler ve aging analizi'],
  },
  sales_risk_analysis: {
    artifactType: 'analysis',
    label: 'Satis Risk ve Performans Analizi',
    outputFormat: 'pdf',
    description: 'Satis hareketlerini iceren Excel dosyalari yukleyin.',
    requiredColumns: ['Tarih', 'Musteri', 'Urun', 'Toplam satis'],
    optionalColumns: ['Bolge', 'Satis temsilcisi', 'Iade durumu'],
    examples: ['Musteri yogunlasma riski'],
  },
  tax_risk_analysis: {
    artifactType: 'analysis',
    label: 'Vergi Risk Analizi',
    outputFormat: 'pdf',
    description: 'Vergi kayitlarini iceren Excel dosyalari yukleyin.',
    requiredColumns: ['Vergi turu', 'Vergi tutari', 'Matrah'],
    optionalColumns: ['Vergi orani', 'Tarih', 'Islem tipi'],
    examples: ['KDV tutarlilik ve aykiri kayit analizi'],
  },
}

type ModeSeed = {
  id: string
  icon: LucideIcon
}

const reportModes: ModeSeed[] = [
  { id: 'income_expense_report', icon: FileText },
  { id: 'cash_flow_report', icon: LineChart },
  { id: 'debt_receivable_report', icon: Landmark },
  { id: 'vat_summary_report', icon: BarChart3 },
  { id: 'personnel_expense_report', icon: FileText },
  { id: 'sales_performance_report', icon: TrendingUp },
  { id: 'profitability_report', icon: LineChart },
  { id: 'current_account_report', icon: FileText },
  { id: 'payroll_cost_report', icon: FileText },
  { id: 'inventory_cost_report', icon: Landmark },
  { id: 'tax_calculation_report', icon: ShieldAlert },
]

const chartModes: ModeSeed[] = [
  { id: 'income_expense_pie_chart', icon: PieChart },
  { id: 'monthly_expense_trend_chart', icon: LineChart },
  { id: 'cashflow_bar_chart', icon: BarChart3 },
  { id: 'top_expenses_chart', icon: BarChart3 },
  { id: 'daily_balance_change_chart', icon: LineChart },
  { id: 'debt_receivable_distribution_chart', icon: Landmark },
  { id: 'sales_performance_chart', icon: TrendingUp },
  { id: 'tax_distribution_chart', icon: PieChart },
]

const analysisModes: ModeSeed[] = [
  { id: 'financial_risk_analysis', icon: ShieldAlert },
  { id: 'cash_runway_analysis', icon: LineChart },
  { id: 'anomaly_spending_analysis', icon: BarChart3 },
  { id: 'expense_optimization_analysis', icon: TrendingUp },
  { id: 'profitability_analysis', icon: LineChart },
  { id: 'receivable_debt_risk_analysis', icon: Landmark },
  { id: 'sales_risk_analysis', icon: TrendingUp },
  { id: 'tax_risk_analysis', icon: ShieldAlert },
]

function toModeItems(items: ModeSeed[]): ModeItem[] {
  return items.map((item) => ({
    id: item.id,
    label: ARTIFACT_INPUT_REQUIREMENTS[item.id].label,
    icon: item.icon,
  }))
}

export const modeGroups: ModeGroup[] = [
  { id: 'report', label: 'Excel Raporlar', icon: FileSpreadsheet, items: toModeItems(reportModes) },
  { id: 'chart', label: 'Grafikler', icon: BarChart3, items: toModeItems(chartModes) },
  { id: 'analysis', label: 'Analizler', icon: FileText, items: toModeItems(analysisModes) },
]

export function isArtifactModeValue(mode: string): boolean {
  return mode in ARTIFACT_INPUT_REQUIREMENTS
}

export function getArtifactModeInfo(mode: string): ArtifactInputRequirement | null {
  return ARTIFACT_INPUT_REQUIREMENTS[mode] ?? null
}
