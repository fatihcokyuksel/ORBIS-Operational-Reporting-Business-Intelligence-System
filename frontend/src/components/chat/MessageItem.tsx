import React, { useState, useRef, useEffect } from 'react'
import { User as UserIcon, Bot, Paperclip, Copy, Check, CheckCircle2, AlertTriangle, XCircle, Download, Info, BookOpen } from 'lucide-react'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  files?: File[]
  fileName?: string
  isStreaming?: boolean
}

interface MessageItemProps {
  msg: Message
  onTick?: () => void
  onDone?: (id: string) => void
}

interface ReportFilterSummary {
  applied?: boolean
  userPrompt?: string | null
  summaryLines?: string[]
  inputRowCount?: number
  filteredRowCount?: number
}

interface ParsedMessageContent {
  mainContent: string
  sources: string[]
}

interface RagAnswerPayload {
  type: 'rag_answer'
  answer: string
  sources?: string[]
  retrievalMode?: string
}

function getArtifactSuccessTitle(artifactType?: string) {
  if (artifactType === 'chart') return 'Grafik Hazır'
  if (artifactType === 'analysis') return 'Analiz Raporu Hazır'
  return 'Rapor Hazır'
}

function getArtifactErrorTitle(artifactType?: string) {
  if (artifactType === 'chart') return 'Grafik Oluşturulamadı'
  if (artifactType === 'analysis') return 'Analiz Raporu Oluşturulamadı'
  return 'Rapor Oluşturulamadı'
}

function getArtifactDownloadLabel(outputFormat?: string) {
  if (outputFormat === 'jpg') return 'JPG İndir'
  if (outputFormat === 'pdf') return 'PDF İndir'
  return 'Excel Raporunu İndir'
}

const TYPEWRITER_DELAY_MS = 18

function splitSourcesFromContent(content: string): ParsedMessageContent {
  const normalized = content.replace(/\r\n/g, '\n')
  const blockMarkers = [
    /\n+---\n\*\*Kaynaklar:\*\*\n?/i,
    /\n+\*\*Kaynaklar:\*\*\n?/i,
    /\n+Kaynaklar:\n?/i,
  ]

  for (const marker of blockMarkers) {
    const match = marker.exec(normalized)
    if (!match) continue

    const mainContent = normalized.slice(0, match.index).trim()
    const sourceBlock = normalized.slice(match.index + match[0].length).trim()
    const sources = sourceBlock
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => line.replace(/^(?:[-*]|\d+\.)\s*/, '').trim())
      .filter(Boolean)

    if (sources.length > 0) {
      return {
        mainContent: mainContent || content,
        sources,
      }
    }
  }

  const singleSourcePatterns = [
    /\n+\*?Kaynak:\*?\s*(.+)$/is,
    /\n+\*{0,2}Kaynaklar:\*{0,2}\s*(.+)$/is,
  ]

  for (const pattern of singleSourcePatterns) {
    const match = pattern.exec(normalized)
    if (!match) continue
    const mainContent = normalized.slice(0, match.index).trim()
    const rawSources = match[1]
      .split(/\n|,\s*/)
      .map((item) => item.trim())
      .filter(Boolean)

    if (rawSources.length > 0) {
      return {
        mainContent: mainContent || content,
        sources: rawSources,
      }
    }
  }

  return {
    mainContent: content,
    sources: [],
  }
}

export function MessageItem({ msg, onTick, onDone }: MessageItemProps) {
  const [isCopied, setIsCopied] = useState(false)
  const [showSources, setShowSources] = useState(false)
  let ragAnswerData: RagAnswerPayload | null = null
  if (msg.role === 'assistant' && msg.content.trim().startsWith('{')) {
    try {
      const parsed = JSON.parse(msg.content)
      if (parsed && parsed.type === 'rag_answer' && typeof parsed.answer === 'string') {
        ragAnswerData = parsed as RagAnswerPayload
      }
    } catch {
      // ignore
    }
  }

  const parsedMessageContent = ragAnswerData
    ? {
        mainContent: ragAnswerData.answer,
        sources: Array.isArray(ragAnswerData.sources) ? ragAnswerData.sources.filter((item) => typeof item === 'string' && item.trim()) : [],
      }
    : splitSourcesFromContent(msg.content)
  const displayContent = parsedMessageContent.mainContent || msg.content
  const sources = parsedMessageContent.sources
  const hasSources = msg.role === 'assistant' && sources.length > 0

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(displayContent)
      setIsCopied(true)
      setTimeout(() => setIsCopied(false), 2000)
    } catch (err) {
      console.error('Kopyalama başarısız:', err)
    }
  }

  // Check if content is a serialized report JSON
  let reportData: any = null
  let isReportJson = false
  if (msg.role === 'assistant' && msg.content.trim().startsWith('{')) {
    try {
      const parsed = JSON.parse(msg.content)
      if (parsed && (parsed.type === 'report_result' || parsed.type === 'report_error')) {
        reportData = parsed
        isReportJson = true
      }
    } catch {
      // ignore
    }
  }

  if (isReportJson && reportData) {
    const isSuccess = reportData.status === 'success' || reportData.status === 'warning'
    const hasWarnings = reportData.warningCount > 0 || (reportData.warnings && reportData.warnings.length > 0)
    const filterSummary = (reportData.filterSummary || null) as ReportFilterSummary | null
    const filterLines = Array.isArray(filterSummary?.summaryLines)
      ? filterSummary.summaryLines.filter((line) => typeof line === 'string' && line.trim().length > 0)
      : []
    if (filterLines.length === 0 && filterSummary?.userPrompt) {
      filterLines.push(filterSummary.userPrompt)
    }
    const hasFilterSummary = Boolean(
      filterSummary && (
        filterLines.length > 0 ||
        typeof filterSummary.inputRowCount === 'number' ||
        typeof filterSummary.filteredRowCount === 'number'
      )
    )
    const hasFilterCounts = Boolean(
      filterSummary &&
      typeof filterSummary.inputRowCount === 'number' &&
      typeof filterSummary.filteredRowCount === 'number'
    )

    if (isSuccess) {
      return (
        <div className="group flex gap-3 w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className="w-7 h-7 rounded-full flex items-center justify-center bg-white text-zinc-900 shrink-0 mt-0.5">
            <Bot size={13} />
          </div>

          <div className="flex-1 max-w-xl bg-zinc-900/40 border border-zinc-800 rounded-2xl p-5 shadow-xl backdrop-blur-md transition-all duration-200 hover:border-zinc-700/80">
            <div className="flex items-center gap-2.5 mb-4 text-emerald-400">
              <CheckCircle2 size={18} className="shrink-0" />
              <h4 className="font-semibold text-[15px] text-zinc-100">{getArtifactSuccessTitle(reportData.artifactType)}</h4>
              {reportData.status === 'warning' && (
                <span className="flex items-center gap-1 text-[10px] text-amber-500 bg-amber-500/10 px-2.5 py-0.5 rounded-full font-semibold border border-amber-500/10">
                  <AlertTriangle size={10} /> Uyarılar Var
                </span>
              )}
            </div>

            <div className="space-y-2.5 text-sm text-zinc-300 border-b border-zinc-800/80 pb-4 mb-4">
              <div className="flex justify-between items-center">
                <span className="text-zinc-500 font-medium">Rapor:</span>
                <span className="font-semibold text-zinc-200">{reportData.displayName}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-zinc-500 font-medium">Durum:</span>
                <span className="font-semibold text-emerald-400">Başarılı</span>
              </div>
              {hasWarnings && (
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500 font-medium">Uyarı Sayısı:</span>
                  <span className="font-semibold text-amber-400">{reportData.warningCount}</span>
                </div>
              )}
              {reportData.createdAt && (
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500 font-medium">Oluşturulma Tarihi:</span>
                  <span className="text-zinc-400 text-xs">
                    {new Date(reportData.createdAt).toLocaleString('tr-TR')}
                  </span>
                </div>
              )}
            </div>

            <a
              href={reportData.downloadUrl}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-500 hover:bg-emerald-600 text-zinc-950 font-bold rounded-xl transition-all duration-150 shadow-md shadow-emerald-500/10 hover:shadow-emerald-500/20 active:scale-[0.98]"
            >
              <Download size={15} />
              {getArtifactDownloadLabel(reportData.outputFormat)}
            </a>

            {hasFilterSummary && (
              <div className="mt-4 pt-4 border-t border-zinc-800/60 animate-in fade-in duration-300">
                <p className="text-xs font-bold text-sky-400 flex items-center gap-1.5 mb-2">
                  <Info size={12} /> Filtre Özeti
                </p>
                {filterLines.length > 0 && (
                  <ul className="space-y-1.5 pl-4 list-disc text-xs text-zinc-300 leading-relaxed">
                    {filterLines.map((line, idx) => (
                      <li key={idx} className="marker:text-sky-400/60">{line}</li>
                    ))}
                  </ul>
                )}
                {hasFilterCounts && (
                  <p className="mt-3 text-xs text-zinc-400 bg-sky-500/5 border border-sky-500/10 px-3 py-2 rounded-xl">
                    {filterSummary?.inputRowCount} satırdan {filterSummary?.filteredRowCount} satır kullanıldı.
                  </p>
                )}
              </div>
            )}

            {hasWarnings && (
              <div className="mt-4 pt-4 border-t border-zinc-800/60 animate-in fade-in duration-300">
                <p className="text-xs font-bold text-amber-500 flex items-center gap-1.5 mb-2">
                  <AlertTriangle size={12} /> Uyarılar
                </p>
                <ul className="space-y-1.5 pl-4 list-disc text-xs text-zinc-400 leading-relaxed">
                  {reportData.warnings.map((warning: any, idx: number) => {
                    const messageText = typeof warning === 'string' 
                      ? warning 
                      : warning.message || `Satır ${warning.row || ''}: ${warning.field || ''} alanında hata.`;
                    return <li key={idx} className="marker:text-amber-500/60">{messageText}</li>
                  })}
                </ul>
              </div>
            )}
          </div>
        </div>
      )
    } else {
      return (
        <div className="group flex gap-3 w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className="w-7 h-7 rounded-full flex items-center justify-center bg-white text-zinc-900 shrink-0 mt-0.5">
            <Bot size={13} />
          </div>

          <div className="flex-1 max-w-xl bg-zinc-900/40 border border-red-950/60 rounded-2xl p-5 shadow-xl backdrop-blur-md transition-all duration-200 hover:border-red-900/50">
            <div className="flex items-center gap-2.5 mb-4 text-red-400">
              <XCircle size={18} className="shrink-0" />
              <h4 className="font-semibold text-[15px] text-zinc-100">{getArtifactErrorTitle(reportData.artifactType)}</h4>
            </div>

            <div className="space-y-2.5 text-sm text-zinc-300 border-b border-zinc-800/80 pb-4 mb-4">
              <div className="flex justify-between items-center">
                <span className="text-zinc-500 font-medium">Rapor:</span>
                <span className="font-semibold text-zinc-200">{reportData.displayName}</span>
              </div>
              <div className="flex flex-col gap-1.5 mt-2">
                <span className="text-zinc-500 font-medium">Hata Mesajı:</span>
                <span className="text-red-400 font-medium leading-relaxed bg-red-500/5 border border-red-500/10 px-3 py-2 rounded-xl text-xs">
                  {reportData.errorMessage}
                </span>
              </div>
            </div>

            {hasFilterSummary && (
              <div className="mb-4 pb-4 border-b border-zinc-800/60 animate-in fade-in duration-300">
                <p className="text-xs font-bold text-sky-400 flex items-center gap-1.5 mb-2">
                  <Info size={12} /> Filtre Özeti
                </p>
                {filterLines.length > 0 && (
                  <ul className="space-y-1.5 pl-4 list-disc text-xs text-zinc-300 leading-relaxed">
                    {filterLines.map((line, idx) => (
                      <li key={idx} className="marker:text-sky-400/60">{line}</li>
                    ))}
                  </ul>
                )}
                {hasFilterCounts && (
                  <p className="mt-3 text-xs text-zinc-400 bg-sky-500/5 border border-sky-500/10 px-3 py-2 rounded-xl">
                    {filterSummary?.inputRowCount} satırdan {filterSummary?.filteredRowCount} satır kaldı.
                  </p>
                )}
              </div>
            )}

            {reportData.details && reportData.details.length > 0 && (
              <div className="mt-3 animate-in fade-in duration-300">
                <p className="text-xs font-bold text-red-400 flex items-center gap-1.5 mb-2">
                  <Info size={12} /> Detaylar
                </p>
                <ul className="space-y-1.5 pl-4 list-disc text-xs text-zinc-400 leading-relaxed">
                  {reportData.details.map((detail: any, idx: number) => {
                    const messageText = typeof detail === 'string'
                      ? detail
                      : detail.message || JSON.stringify(detail);
                    return <li key={idx} className="marker:text-red-500/60">{messageText}</li>
                  })}
                </ul>
              </div>
            )}
          </div>
        </div>
      )
    }
  }

  return (
    <div
      className={cn(
        "group flex gap-3 w-full animate-in fade-in slide-in-from-bottom-2 duration-300",
        msg.role === 'user' ? "flex-row-reverse" : "flex-row"
      )}
    >
      <div className={cn(
        "w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5",
        msg.role === 'user'
          ? "bg-zinc-700 text-zinc-200"
          : "bg-white text-zinc-900"
      )}>
        {msg.role === 'user' ? <UserIcon size={13} /> : <Bot size={13} />}
      </div>

      <div className={cn(
        "flex flex-col gap-1 min-w-0",
        msg.role === 'user' ? "items-end max-w-[75%]" : "items-start w-full"
      )}>
        {((msg.files && msg.files.length > 0) || msg.fileName) && (
          <div className="flex flex-col gap-2 bg-zinc-800 border border-zinc-700 text-zinc-300 px-3 py-2 rounded-lg text-sm mb-2">
            {(msg.files && msg.files.length > 0 ? msg.files.map((file) => file.name) : String(msg.fileName).split(',').map((item) => item.trim()).filter(Boolean)).map((name) => (
              <div key={name} className="flex items-center gap-2 min-w-0">
                <Paperclip size={12} className="text-zinc-500 shrink-0" />
                <span className="truncate">{name}</span>
              </div>
            ))}
          </div>
        )}
        {displayContent && (
          <div className="flex flex-col w-full relative">
            <div className={cn(
              "text-[15px] leading-7",
              msg.role === 'user'
                ? "bg-zinc-800 text-zinc-100 px-4 py-2.5 rounded-2xl rounded-tr-md [word-break:break-word] [overflow-wrap:anywhere] whitespace-pre-wrap inline-block"
                : "text-zinc-200 w-full [word-break:break-word] [overflow-wrap:anywhere] prose prose-sm prose-invert max-w-none prose-p:leading-7 prose-p:my-2 prose-headings:text-zinc-100 prose-th:text-left prose-table:w-full prose-code:text-zinc-300 prose-code:bg-zinc-800 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-pre:bg-zinc-900 prose-pre:border prose-pre:border-zinc-800 prose-pre:overflow-x-auto"
            )}>
              {msg.role === 'user' ? (
                displayContent
              ) : (
                <TypewriterMarkdown
                  content={displayContent}
                  enabled={Boolean(msg.isStreaming)}
                  onTick={() => onTick && onTick()}
                  onDone={() => onDone && onDone(msg.id)}
                />
              )}
            </div>
            
            {!msg.isStreaming && (
              <div className={cn(
                "mt-2 flex items-center gap-2",
                msg.role === 'user' ? "justify-end" : "justify-start"
              )}>
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 transition-colors"
                  title="Metni Kopyala"
                >
                  {isCopied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                  {isCopied ? 'Kopyalandı' : 'Kopyala'}
                </button>
                {hasSources && (
                  <button
                    onClick={() => setShowSources((prev) => !prev)}
                    className={cn(
                      "flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium transition-colors",
                      showSources
                        ? "text-sky-300 bg-sky-500/10"
                        : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
                    )}
                    title="Kaynakları göster"
                  >
                    <BookOpen size={13} />
                    {showSources ? 'Kaynakları Gizle' : `Kaynaklar (${sources.length})`}
                  </button>
                )}
              </div>
            )}
            {hasSources && showSources && !msg.isStreaming && (
              <div className={cn(
                "mt-2 rounded-xl border border-sky-500/15 bg-sky-500/5 px-3 py-3 text-xs text-zinc-300",
                msg.role === 'user' ? "self-end" : "self-start"
              )}>
                <p className="mb-2 flex items-center gap-1.5 font-semibold text-sky-300">
                  <BookOpen size={13} />
                  Kaynaklar
                </p>
                <ul className="space-y-1.5 pl-4 list-disc leading-relaxed">
                  {sources.map((source, idx) => (
                    <li key={`${source}-${idx}`} className="marker:text-sky-400/60">{source}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function TypewriterMarkdown({
  content,
  enabled,
  onTick,
  onDone,
}: {
  content: string
  enabled: boolean
  onTick: () => void
  onDone: () => void
}) {
  const [visibleContent, setVisibleContent] = useState(enabled ? '' : content)
  const onTickRef = useRef(onTick)
  const onDoneRef = useRef(onDone)

  useEffect(() => {
    onTickRef.current = onTick
    onDoneRef.current = onDone
  }, [onTick, onDone])

  useEffect(() => {
    if (!enabled) return

    let index = 0
    const intervalId = window.setInterval(() => {
      index += 1
      setVisibleContent(content.slice(0, index))
      onTickRef.current()

      if (index >= content.length) {
        window.clearInterval(intervalId)
        onDoneRef.current()
      }
    }, TYPEWRITER_DELAY_MS)

    return () => window.clearInterval(intervalId)
  }, [content, enabled])

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]}>
      {enabled ? visibleContent : content}
    </ReactMarkdown>
  )
}
