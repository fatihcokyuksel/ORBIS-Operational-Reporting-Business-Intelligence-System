import React, { useMemo, useRef, useState } from 'react'
import { ArrowUp, Loader2, Paperclip } from 'lucide-react'
import { cn } from '@/lib/utils'
import { FileUploadZone } from './FileUploadZone'
import { getArtifactModeInfo, isArtifactModeValue } from './modeCatalog'

interface ChatInputProps {
  onSend: (text: string, files: File[]) => Promise<void> | void
  isProcessing: boolean
  currentMode: string
}

const MAX_CHARS = 5000

export function ChatInput({ onSend, isProcessing, currentMode }: ChatInputProps) {
  const [input, setInput] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [showUpload, setShowUpload] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const artifactInfo = getArtifactModeInfo(currentMode)
  const isArtifactMode = isArtifactModeValue(currentMode)
  const requiresExcel = artifactInfo?.artifactType !== 'chart'
  const shouldShowUpload = showUpload || selectedFiles.length > 0 || isArtifactMode
  const atLimit = input.length >= MAX_CHARS

  const canSend = useMemo(() => {
    if (isProcessing || atLimit) return false
    if (isArtifactMode && requiresExcel) return selectedFiles.length > 0
    if (isArtifactMode && !requiresExcel) return selectedFiles.length > 0 || input.trim().length > 0
    return input.trim().length > 0 || selectedFiles.length > 0
  }, [atLimit, input, isArtifactMode, isProcessing, requiresExcel, selectedFiles.length])

  const handleSendClick = async () => {
    if (!canSend) return
    const userText = input
    const fileRefs = selectedFiles

    setInput('')
    setSelectedFiles([])
    setShowUpload(false)
    if (textareaRef.current) {
      textareaRef.current.style.height = '36px'
    }

    await onSend(userText, fileRefs)
  }

  return (
    <div className="shrink-0 px-2 sm:px-4 pb-4 sm:pb-5 pt-2 sm:pt-3">
      <div className="max-w-3xl mx-auto w-full">
        {shouldShowUpload && (
          <div className="mb-3">
            <FileUploadZone
              selectedFiles={selectedFiles}
              onFilesChange={setSelectedFiles}
              onRemoveFile={(index) => setSelectedFiles((prev) => prev.filter((_, fileIndex) => fileIndex !== index))}
              isArtifactMode={isArtifactMode}
              artifactInfo={artifactInfo}
            />
          </div>
        )}

        <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-2xl focus-within:border-zinc-700 transition-colors duration-200 px-2 py-2">
          {!isArtifactMode && (
            <button
              onClick={() => setShowUpload((prev) => !prev)}
              className={cn(
                'shrink-0 w-9 h-9 flex items-center justify-center rounded-xl transition-all duration-150',
                showUpload || selectedFiles.length > 0
                  ? 'text-zinc-200 bg-zinc-700'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800'
              )}
              title="Dosya ekle"
            >
              <Paperclip size={17} />
            </button>
          )}

          <textarea
            ref={textareaRef}
            value={input}
            onChange={(event) => {
              const value = event.target.value
              if (value.length > MAX_CHARS) return
              setInput(value)
              event.target.style.height = 'auto'
              event.target.style.height = `${Math.min(event.target.scrollHeight, 200)}px`
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void handleSendClick()
              }
            }}
            placeholder={
              isArtifactMode
                ? artifactInfo?.supportsPromptOnly
                  ? 'Excel dosyalarini yukleyin veya destekliyorsa veriyi prompt ile yazin.'
                  : 'Secili artifact icin .xlsx dosyalari yukleyin.'
                : 'Finansal verileri yapistirin veya isteginizi yazin...'
            }
            className="flex-1 bg-transparent border-none focus:outline-none focus:ring-0 resize-none text-[15px] text-zinc-200 placeholder:text-zinc-500 min-h-[52px] sm:min-h-[36px] max-h-[200px] leading-[1.6] overflow-y-auto py-1.5 align-middle"
            rows={1}
            style={{ height: 'auto' }}
          />

          <button
            onClick={() => void handleSendClick()}
            disabled={!canSend}
            className={cn(
              'shrink-0 flex items-center justify-center bg-white text-zinc-900 rounded-xl hover:bg-zinc-100 disabled:opacity-25 disabled:cursor-not-allowed transition-all duration-150',
              isArtifactMode ? 'h-9 px-3.5' : 'w-9 h-9'
            )}
          >
            {isProcessing ? (
              <Loader2 size={15} className="animate-spin" />
            ) : isArtifactMode ? (
              <span className="text-xs font-bold whitespace-nowrap">Olustur</span>
            ) : (
              <ArrowUp size={15} />
            )}
          </button>
        </div>

        <div className="flex flex-col sm:relative sm:flex-row items-center justify-center mt-2 px-1 gap-1">
          <p className="text-[10px] sm:text-xs text-zinc-600 text-center">
            {isArtifactMode
              ? 'Uretilen artifact kayit altina alinir; secili alanda sadece .xlsx dosyalari kabul edilir.'
              : 'ORBIS hata yapabilir. Onemli finansal verileri dogrulayin.'}
          </p>
          {input.length > 0 && (
            <p
              className={cn(
                'sm:absolute sm:right-1 text-[10px] sm:text-xs tabular-nums transition-colors',
                atLimit ? 'text-red-400' : input.length > MAX_CHARS * 0.9 ? 'text-yellow-500' : 'text-zinc-600'
              )}
            >
              {input.length.toLocaleString()} / {MAX_CHARS.toLocaleString()}
            </p>
          )}
        </div>
        {atLimit && (
          <p className="text-xs text-red-400 text-center mt-1">
            En fazla {MAX_CHARS.toLocaleString()} karakter yazabilirsiniz
          </p>
        )}
      </div>
    </div>
  )
}
