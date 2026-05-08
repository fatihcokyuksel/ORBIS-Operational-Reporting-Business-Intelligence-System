"use client"

import React, { useRef, useState } from 'react'
import { UploadCloud, X, File as FileIcon, FileText, Image as ImageIcon, FileSpreadsheet } from 'lucide-react'
import { cn } from '@/lib/utils'

interface FileUploadZoneProps {
  onFileSelect: (file: File) => void
  selectedFile: File | null
  onClearFile: () => void
}

export function FileUploadZone({ onFileSelect, selectedFile, onClearFile }: FileUploadZoneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFileSelect(e.target.files[0])
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFileSelect(e.dataTransfer.files[0])
    }
  }

  const getFileIcon = (type: string) => {
    if (type.includes('pdf')) return <FileText className="text-red-500" />
    if (type.includes('image')) return <ImageIcon className="text-blue-500" />
    if (type.includes('spreadsheet') || type.includes('excel') || type.includes('csv')) return <FileSpreadsheet className="text-green-500" />
    return <FileIcon className="text-zinc-500" />
  }

  if (selectedFile) {
    return (
      <div className="flex items-center justify-between p-3 mb-4 bg-zinc-900 border border-zinc-800 rounded-xl">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="p-2 bg-zinc-800 rounded-lg shadow-sm">
            {getFileIcon(selectedFile.type)}
          </div>
          <div className="flex flex-col truncate">
            <span className="text-sm font-medium text-zinc-200 truncate">{selectedFile.name}</span>
            <span className="text-xs text-zinc-400">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</span>
          </div>
        </div>
        <button 
          onClick={onClearFile}
          className="p-1.5 hover:bg-zinc-800 rounded-full text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <X size={16} />
        </button>
      </div>
    )
  }

  return (
    <div 
      className={cn(
        "mb-4 border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center transition-all duration-200 cursor-pointer",
        isDragging ? "border-zinc-500 bg-zinc-800/50" : "border-zinc-700 bg-zinc-900/50 hover:bg-zinc-900 hover:border-zinc-600"
      )}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      onClick={() => fileInputRef.current?.click()}
    >
      <input 
        type="file" 
        className="hidden" 
        ref={fileInputRef} 
        onChange={handleFileChange}
        accept=".pdf,.csv,.xlsx,.xls,image/*"
      />
      <div className="w-10 h-10 mb-3 bg-zinc-800 shadow-sm rounded-full flex items-center justify-center text-zinc-400">
        <UploadCloud size={20} />
      </div>
      <p className="text-sm font-medium text-zinc-300 mb-1">Click to upload or drag and drop</p>
      <p className="text-xs text-zinc-500">PDF, Excel, CSV or Images (max. 10MB)</p>
    </div>
  )
}
