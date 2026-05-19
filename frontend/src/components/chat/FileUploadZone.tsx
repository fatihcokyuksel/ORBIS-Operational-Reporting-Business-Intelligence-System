"use client"

import React, { useMemo, useRef, useState } from 'react'
import { FileSpreadsheet, Paperclip, UploadCloud, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ArtifactInputRequirement } from './modeCatalog'
import { MAX_ARTIFACT_FILE_SIZE_MB, MAX_ARTIFACT_FILES } from './modeCatalog'

interface FileUploadZoneProps {
  selectedFiles: File[]
  onFilesChange: (files: File[]) => void
  onRemoveFile: (index: number) => void
  isArtifactMode?: boolean
  artifactInfo?: ArtifactInputRequirement | null
}

function validateArtifactFiles(files: File[]): string | null {
  if (files.length > MAX_ARTIFACT_FILES) {
    return `En fazla ${MAX_ARTIFACT_FILES} Excel dosyasi yukleyebilirsiniz.`
  }
  for (const file of files) {
    if (!file.name.toLowerCase().endsWith('.xlsx')) {
      return 'Sadece .xlsx uzantili Excel dosyalari kabul edilir.'
    }
    if (file.size > MAX_ARTIFACT_FILE_SIZE_MB * 1024 * 1024) {
      return `Her dosya en fazla ${MAX_ARTIFACT_FILE_SIZE_MB} MB olabilir.`
    }
  }
  return null
}

export function FileUploadZone({
  selectedFiles,
  onFilesChange,
  onRemoveFile,
  isArtifactMode,
  artifactInfo,
}: FileUploadZoneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const accept = isArtifactMode ? '.xlsx' : '.pdf,.csv,.xlsx,.xls,image/*'
  const multiple = Boolean(isArtifactMode)
  const helperText = isArtifactMode
    ? `Sadece Excel dosyasi (.xlsx) kabul edilir. En fazla ${MAX_ARTIFACT_FILES} dosya, dosya basina ${MAX_ARTIFACT_FILE_SIZE_MB} MB.`
    : 'PDF, Excel, CSV veya gorsel dosyalar (en fazla 10 MB)'

  const requirementLines = useMemo(() => {
    if (!artifactInfo) return []
    return [
      ...artifactInfo.requiredColumns.map((item) => ({ label: item, tone: 'required' as const })),
      ...artifactInfo.optionalColumns.map((item) => ({ label: item, tone: 'optional' as const })),
    ]
  }, [artifactInfo])

  const pushFiles = (incoming: FileList | File[]) => {
    const nextFiles = Array.from(incoming)
    const merged = isArtifactMode ? [...selectedFiles, ...nextFiles] : nextFiles.slice(0, 1)
    const deduped = dedupeFiles(merged)
    const validationMessage = isArtifactMode ? validateArtifactFiles(deduped) : null
    if (validationMessage) {
      setError(validationMessage)
      return
    }
    setError(null)
    onFilesChange(deduped)
  }
  return (
    <div className="mb-2 space-y-2">
      {isArtifactMode && artifactInfo && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-500">Veri Gereksinimi</p>
          <h3 className="mt-0.5 text-xs font-bold text-zinc-100">{artifactInfo.label}</h3>
          <p className="mt-1 text-[11px] leading-relaxed text-zinc-400">{artifactInfo.description}</p>
          
          <div className="mt-2.5 border border-zinc-800/80 rounded-lg overflow-hidden bg-zinc-950/40 text-[10px] sm:text-[11px]">
            <div className="grid grid-cols-[85px_1fr] border-b border-zinc-800/80">
              <div className="px-2 py-1 font-semibold text-zinc-400 bg-zinc-900/30 border-r border-zinc-800/80 shrink-0">
                Gerekli
              </div>
              <div className="px-2.5 py-1 text-zinc-200">
                {artifactInfo.requiredColumns.join(', ')}
              </div>
            </div>
            {artifactInfo.optionalColumns.length > 0 && (
              <div className="grid grid-cols-[85px_1fr] border-b border-zinc-800/80">
                <div className="px-2 py-1 font-semibold text-zinc-400 bg-zinc-900/30 border-r border-zinc-800/80 shrink-0">
                  Opsiyonel
                </div>
                <div className="px-2.5 py-1 text-zinc-200">
                  {artifactInfo.optionalColumns.join(', ')}
                </div>
              </div>
            )}
            {artifactInfo.examples.length > 0 && (
              <div className="grid grid-cols-[85px_1fr]">
                <div className="px-2 py-1 font-semibold text-zinc-400 bg-zinc-900/30 border-r border-zinc-800/80 shrink-0">
                  Örnek
                </div>
                <div className="px-2.5 py-1 text-zinc-300 leading-relaxed">
                  {artifactInfo.examples.join(', ')}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <div
        className={cn(
          'border-2 border-dashed rounded-xl py-3 px-4 flex flex-col items-center justify-center transition-all duration-200 cursor-pointer',
          isDragging ? 'border-zinc-500 bg-zinc-800/50' : 'border-zinc-700 bg-zinc-900/50 hover:bg-zinc-900 hover:border-zinc-600',
          error && 'border-red-500 bg-red-500/5'
        )}
        onDragOver={(event) => {
          event.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setIsDragging(false)
          pushFiles(event.dataTransfer.files)
        }}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept={accept}
          multiple={multiple}
          onChange={(event) => {
            if (event.target.files && event.target.files.length > 0) {
              pushFiles(event.target.files)
            }
            event.currentTarget.value = ''
          }}
        />
        <div className={cn('w-8 h-8 mb-1.5 rounded-full flex items-center justify-center', error ? 'bg-red-500/10 text-red-400' : 'bg-zinc-800 text-zinc-400')}>
          <UploadCloud size={16} />
        </div>
        <p className="text-xs font-medium text-zinc-300 mb-0.5">
          {error ? 'Hatali Dosya Tipi' : 'Yuklemek icin tiklayin veya surukleyip birakin'}
        </p>
        <p className="text-[10px] text-zinc-500 text-center max-w-xl">{helperText}</p>
        {error && <p className="mt-1.5 text-xs font-semibold text-red-400">{error}</p>}
      </div>

      {selectedFiles.length > 0 && (
        <div className="space-y-1.5">
          {selectedFiles.map((file, index) => (
            <div key={`${file.name}-${file.size}-${index}`} className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900 px-2.5 py-1.5">
              <div className="flex items-center gap-2 overflow-hidden">
                <div className="rounded bg-zinc-800 p-1.5 text-emerald-400">
                  {isArtifactMode ? <FileSpreadsheet size={14} /> : <Paperclip size={14} />}
                </div>
                <div className="truncate">
                  <p className="truncate text-xs font-medium text-zinc-200">{file.name}</p>
                  <p className="text-[10px] text-zinc-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
              </div>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation()
                  setError(null)
                  onRemoveFile(index)
                }}
                className="rounded-full p-1 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
                title="Dosyayi kaldir"
              >
                <X size={13} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function dedupeFiles(files: File[]) {
  const seen = new Set<string>()
  return files.filter((file) => {
    const key = `${file.name}-${file.size}-${file.lastModified}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  }).slice(0, MAX_ARTIFACT_FILES)
}
