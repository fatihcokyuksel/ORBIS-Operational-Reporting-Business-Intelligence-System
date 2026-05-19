"use client"

import React, { useState, useEffect } from 'react'
import {
  FileSpreadsheet, Search, CheckCircle2, AlertTriangle, XCircle, Download,
  ChevronDown, ChevronUp, Loader2, Info
} from 'lucide-react'
import Link from 'next/link'
import { cn } from '@/lib/utils'

interface ReportFilterSummary {
  applied?: boolean
  userPrompt?: string | null
  summaryLines?: string[]
  inputRowCount?: number
  filteredRowCount?: number
}

interface Report {
  id: string
  artifactType?: 'report' | 'chart' | 'analysis'
  artifactId?: string
  reportType: string
  displayName: string
  status: 'success' | 'warning' | 'failed'
  createdAt: string
  fileName?: string
  downloadUrl?: string
  outputFormat?: string
  sourceFileName?: string
  warningCount: number
  warnings: string[]
  errorMessage?: string
  filterSummary?: ReportFilterSummary | null
}

function getFilterLines(filterSummary?: ReportFilterSummary | null): string[] {
  const lines = Array.isArray(filterSummary?.summaryLines)
    ? filterSummary.summaryLines.filter((line) => typeof line === 'string' && line.trim().length > 0)
    : []

  if (lines.length === 0 && filterSummary?.userPrompt) {
    lines.push(filterSummary.userPrompt)
  }

  return lines
}

function hasFilterCounts(filterSummary?: ReportFilterSummary | null): boolean {
  return Boolean(
    filterSummary &&
    typeof filterSummary.inputRowCount === 'number' &&
    typeof filterSummary.filteredRowCount === 'number'
  )
}

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedType, setSelectedType] = useState('all')
  const [selectedStatus, setSelectedStatus] = useState('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    async function fetchReports() {
      try {
        const res = await fetch('/api/reports')
        if (res.ok) {
          const data = await res.json()
          if (data && Array.isArray(data.reports)) {
            setReports(data.reports)
          }
        }
      } catch (err) {
        console.error('Raporlar yüklenemedi:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchReports()
  }, [])

  const reportTypes = [
    { id: 'all', label: 'Tüm Rapor Tipleri' },
    { id: 'income_expense_report', label: 'Gelir Gider Raporu' },
    { id: 'cash_flow_report', label: 'Nakit Akış Raporu' },
    { id: 'debt_receivable_report', label: 'Borç-Alacak Raporu' },
    { id: 'vat_summary_report', label: 'KDV Özet Raporu' },
    { id: 'personnel_expense_report', label: 'Personel Gider Analiz Raporu' },
    { id: 'sales_performance_report', label: 'Satış Performans Raporu' },
    { id: 'profitability_report', label: 'Nakit Bazlı Karlılık Raporu' },
    { id: 'current_account_report', label: 'Cari Hesap Takip Raporu' },
    { id: 'payroll_cost_report', label: 'Maaş ve Personel Maliyet Raporu' },
    { id: 'inventory_cost_report', label: 'Stok Maliyet Raporu' },
    { id: 'tax_calculation_report', label: 'Vergi Hesaplama Raporu' },
  ]

  const statusOptions = [
    { id: 'all', label: 'Tüm Durumlar' },
    { id: 'success', label: 'Başarılı' },
    { id: 'warning', label: 'Uyarı Var' },
    { id: 'failed', label: 'Başarısız' },
  ]

  const filteredReports = reports.filter((report) => {
    const matchesSearch =
      report.displayName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (report.sourceFileName && report.sourceFileName.toLowerCase().includes(searchTerm.toLowerCase()))
    const matchesType = selectedType === 'all' || report.reportType === selectedType || report.artifactId === selectedType
    const matchesStatus = selectedStatus === 'all' || report.status === selectedStatus
    return matchesSearch && matchesType && matchesStatus
  })

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id)
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-zinc-950 text-zinc-100 overflow-y-auto px-4 sm:px-8 py-6 sm:py-8 pt-16 sm:pt-8">
      {/* Header */}
      <div className="max-w-5xl mx-auto w-full mb-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              <FileSpreadsheet className="text-emerald-500 w-8 h-8 shrink-0" />
              Rapor Geçmişi
            </h1>
            <p className="text-zinc-500 text-sm mt-1 max-w-2xl leading-relaxed">
              Geçmişte ürettiğiniz tüm denetim ve finansal analiz raporlarını buradan inceleyebilir, filtreleyebilir ve bilgisayarınıza indirebilirsiniz.
            </p>
          </div>
        </div>
      </div>

      {/* Filters Card */}
      <div className="max-w-5xl mx-auto w-full bg-zinc-900/40 border border-zinc-800/80 rounded-2xl p-4 sm:p-5 shadow-lg backdrop-blur-md mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Search */}
          <div className="relative">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              placeholder="Rapor veya kaynak dosya adı..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-10 pr-4 py-2 text-sm text-zinc-200 placeholder:text-zinc-650 focus:outline-none focus:border-zinc-700 transition-colors"
            />
          </div>

          {/* Rapor Tipi Filter */}
          <div>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2 text-sm text-zinc-300 focus:outline-none focus:border-zinc-700 transition-colors cursor-pointer"
            >
              {reportTypes.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          {/* Durum Filter */}
          <div>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2 text-sm text-zinc-300 focus:outline-none focus:border-zinc-700 transition-colors cursor-pointer"
            >
              {statusOptions.map((status) => (
                <option key={status.id} value={status.id}>
                  {status.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Reports Table/List Container */}
      <div className="max-w-5xl mx-auto w-full flex-1">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
            <p className="text-sm text-zinc-500">Rapor geçmişiniz yükleniyor...</p>
          </div>
        ) : filteredReports.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-center py-20 px-4 bg-zinc-900/20 border border-dashed border-zinc-800 rounded-2xl">
            <div className="w-14 h-14 bg-zinc-900 rounded-full flex items-center justify-center text-zinc-600 border border-zinc-800 mb-4">
              <FileSpreadsheet size={28} />
            </div>
            <h3 className="text-base font-semibold text-zinc-200 mb-1">Rapor Bulunamadı</h3>
            <p className="text-sm text-zinc-500 max-w-sm leading-relaxed mb-6">
              {reports.length === 0
                ? "Henüz sistemde üretilmiş bir raporunuz bulunmuyor. İlk raporunuzu oluşturmak için yapay zeka asistanını kullanabilirsiniz."
                : "Seçtiğiniz filtreleme kriterlerine uygun bir rapor kaydı bulunamadı."}
            </p>
            {reports.length === 0 && (
              <Link
                href="/"
                className="inline-flex items-center gap-2 bg-white hover:bg-zinc-100 text-zinc-950 font-bold px-5 py-2.5 rounded-xl transition-all duration-150 shadow-md shadow-white/5 active:scale-[0.98]"
              >
                Rapor Üretmeye Başla
              </Link>
            )}
          </div>
        ) : (
          <div className="bg-zinc-900/40 border border-zinc-800/80 rounded-2xl overflow-hidden shadow-xl backdrop-blur-md mb-8">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-zinc-800/80 bg-zinc-950/40 text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    <th className="py-4 px-5">Rapor Adı</th>
                    <th className="py-4 px-5">Durum</th>
                    <th className="py-4 px-5">Oluşturulma Tarihi</th>
                    <th className="py-4 px-5">Kaynak Dosya</th>
                    <th className="py-4 px-5 text-right">İşlemler</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {filteredReports.map((report) => {
                    const isExpanded = expandedId === report.id
                    const isSuccess = report.status === 'success' || report.status === 'warning'
                    const hasWarnings = report.warningCount > 0 || (report.warnings && report.warnings.length > 0)
                    const filterLines = getFilterLines(report.filterSummary)
                    const hasReportFilterSummary = Boolean(
                      report.filterSummary &&
                      (filterLines.length > 0 || hasFilterCounts(report.filterSummary))
                    )

                    return (
                      <React.Fragment key={report.id}>
                        {/* Table Row */}
                        <tr className={cn(
                          "text-sm transition-colors hover:bg-zinc-800/30 cursor-pointer",
                          isExpanded && "bg-zinc-800/20"
                        )}
                        onClick={() => toggleExpand(report.id)}
                        >
                          <td className="py-4 px-5 font-semibold text-zinc-100">
                            <div className="flex items-center gap-2.5">
                              <FileSpreadsheet className="text-zinc-500 w-4 h-4 shrink-0" />
                              {report.displayName}
                            </div>
                          </td>
                          <td className="py-4 px-5">
                            {report.status === 'success' && (
                              <span className="inline-flex items-center gap-1 text-[11px] text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full font-semibold border border-emerald-500/10">
                                <CheckCircle2 size={11} /> Başarılı
                              </span>
                            )}
                            {report.status === 'warning' && (
                              <span className="inline-flex items-center gap-1 text-[11px] text-amber-500 bg-amber-500/10 px-2.5 py-0.5 rounded-full font-semibold border border-amber-500/10">
                                <AlertTriangle size={11} /> Uyarı Var
                              </span>
                            )}
                            {report.status === 'failed' && (
                              <span className="inline-flex items-center gap-1 text-[11px] text-red-400 bg-red-500/10 px-2.5 py-0.5 rounded-full font-semibold border border-red-500/10">
                                <XCircle size={11} /> Başarısız
                              </span>
                            )}
                          </td>
                          <td className="py-4 px-5 text-zinc-400 text-xs">
                            {new Date(report.createdAt).toLocaleString('tr-TR')}
                          </td>
                          <td className="py-4 px-5 text-zinc-500 max-w-[150px] truncate text-xs" title={report.sourceFileName}>
                            {report.sourceFileName || '-'}
                          </td>
                          <td className="py-4 px-5 text-right" onClick={(e) => e.stopPropagation()}>
                            <div className="flex items-center justify-end gap-2">
                              {/* Expand toggle */}
                              <button
                                onClick={() => toggleExpand(report.id)}
                                className="p-1.5 hover:bg-zinc-800 text-zinc-450 hover:text-zinc-200 rounded-lg transition-colors"
                                title="Detayları göster"
                              >
                                {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                              </button>

                              {/* Download link */}
                              {isSuccess ? (
                                <a
                                  href={report.downloadUrl}
                                  download
                                  className="flex items-center gap-1 bg-emerald-500 hover:bg-emerald-600 text-zinc-955 font-bold px-3 py-1.5 rounded-xl text-xs shadow-md shadow-emerald-500/5 transition-all active:scale-95 cursor-pointer"
                                  title="Excel olarak indir"
                                >
                                  <Download size={12} /> İndir
                                </a>
                              ) : (
                                <button
                                  onClick={() => toggleExpand(report.id)}
                                  className="flex items-center gap-1 bg-zinc-850 hover:bg-zinc-700 text-zinc-300 font-semibold px-3 py-1.5 rounded-xl text-xs border border-zinc-750 transition-colors"
                                  title="Hata detayını gör"
                                >
                                  <Info size={12} /> Detaylar
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>

                        {/* Expanded details row */}
                        {isExpanded && (
                          <tr>
                            <td colSpan={5} className="bg-zinc-900/60 p-5 border-t border-b border-zinc-800/80 animate-in fade-in duration-200">
                              <div className="max-w-2xl text-left">
                                {report.status === 'failed' ? (
                                  <div>
                                    <h5 className="text-xs font-bold text-red-400 uppercase tracking-wider flex items-center gap-1.5 mb-2">
                                      <XCircle size={13} /> Rapor Oluşturma Hatası
                                    </h5>
                                    <p className="text-sm text-zinc-300 leading-relaxed bg-red-500/5 border border-red-500/10 p-3 rounded-xl mb-3 font-medium">
                                      {report.errorMessage}
                                    </p>
                                    {hasReportFilterSummary && (
                                      <div className="mb-3">
                                        <h5 className="text-xs font-bold text-sky-400 uppercase tracking-wider flex items-center gap-1.5 mb-2">
                                          <Info size={12} /> Filtre Özeti
                                        </h5>
                                        {filterLines.length > 0 && (
                                          <ul className="space-y-1.5 pl-4 list-disc text-xs text-zinc-300 leading-relaxed">
                                            {filterLines.map((line, idx) => (
                                              <li key={idx} className="marker:text-sky-400/60">{line}</li>
                                            ))}
                                          </ul>
                                        )}
                                        {hasFilterCounts(report.filterSummary) && (
                                          <p className="mt-3 text-xs text-zinc-400 bg-sky-500/5 border border-sky-500/10 p-3 rounded-xl">
                                            {report.filterSummary?.inputRowCount} satırdan {report.filterSummary?.filteredRowCount} satır kaldı.
                                          </p>
                                        )}
                                      </div>
                                    )}
                                    {report.warnings && report.warnings.length > 0 && (
                                      <div className="mt-3">
                                        <p className="text-xs font-bold text-zinc-400 flex items-center gap-1.5 mb-2">
                                          <Info size={12} /> Hata Ayrıntıları
                                        </p>
                                        <ul className="space-y-1.5 pl-4 list-disc text-xs text-zinc-400">
                                          {report.warnings.map((detail, idx) => (
                                            <li key={idx} className="marker:text-red-500/50">{detail}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                  </div>
                                ) : (
                                  <div>
                                    <div className="flex flex-col sm:flex-row sm:justify-between gap-4 mb-4 pb-4 border-b border-zinc-800/40">
                                      <div>
                                        <h5 className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Rapor Kimliği</h5>
                                        <p className="text-xs font-mono text-zinc-455 mt-1 select-all">{report.id}</p>
                                      </div>
                                      <div>
                                        <h5 className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Dosya Adı</h5>
                                        <p className="text-xs text-zinc-300 mt-1">{report.fileName || '-'}</p>
                                      </div>
                                    </div>

                                    {hasReportFilterSummary && (
                                      <div className="mb-4 pb-4 border-b border-zinc-800/40">
                                        <h5 className="text-xs font-bold text-sky-400 uppercase tracking-wider flex items-center gap-1.5 mb-2">
                                          <Info size={12} /> Filtre Özeti
                                        </h5>
                                        {filterLines.length > 0 && (
                                          <ul className="space-y-1.5 pl-4 list-disc text-xs text-zinc-300 leading-relaxed">
                                            {filterLines.map((line, idx) => (
                                              <li key={idx} className="marker:text-sky-400/60">{line}</li>
                                            ))}
                                          </ul>
                                        )}
                                        {hasFilterCounts(report.filterSummary) && (
                                          <p className="mt-3 text-xs text-zinc-400 bg-sky-500/5 border border-sky-500/10 p-3 rounded-xl">
                                            {report.filterSummary?.inputRowCount} satırdan {report.filterSummary?.filteredRowCount} satır kullanıldı.
                                          </p>
                                        )}
                                      </div>
                                    )}
                                    
                                    {hasWarnings ? (
                                      <div>
                                        <h5 className="text-xs font-bold text-amber-500 uppercase tracking-wider flex items-center gap-1.5 mb-2">
                                          <AlertTriangle size={13} /> Rapor Doğrulama Uyarıları ({report.warningCount})
                                        </h5>
                                        <ul className="space-y-1.5 pl-4 list-disc text-xs text-zinc-400 leading-relaxed">
                                          {report.warnings.map((warning, idx) => (
                                            <li key={idx} className="marker:text-amber-500/50">{warning}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    ) : (
                                      <div className="flex items-center gap-2 text-emerald-400 text-xs bg-emerald-500/5 border border-emerald-500/10 px-3.5 py-2.5 rounded-xl font-medium">
                                        <CheckCircle2 size={14} />
                                        Bu rapor, veri doğrulama kurallarından 100% başarıyla geçti. Herhangi bir uyarı veya tutarsızlık tespit edilmedi.
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
