"use client"

import React, { useState, useRef, useEffect } from 'react'
import { ModeSelector, type ActionMode } from './ModeSelector'
import { FileUploadZone } from './FileUploadZone'
import { Send, User as UserIcon, Bot, Loader2, Paperclip, ArrowUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  file?: File | null
}

export function ChatInterface() {
  const [currentMode, setCurrentMode] = useState<ActionMode>('revenue')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Hello! I am your FinAI Assistant. Please select an operation mode above and describe your request or upload a financial document to get started.'
    }
  ])
  const [isProcessing, setIsProcessing] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [showUpload, setShowUpload] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isProcessing])

  const handleSend = () => {
    if (!input.trim() && !selectedFile) return

    const newUserMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      file: selectedFile
    }

    setMessages(prev => [...prev, newUserMsg])
    setInput('')
    setSelectedFile(null)
    setShowUpload(false)
    setIsProcessing(true)

    // Simulate AI processing
    setTimeout(() => {
      let aiResponse = ''
      
      if (currentMode === 'revenue') {
        aiResponse = '### Revenue-Expense Summary\n\nBased on your prompt, here is a breakdown:\n\n| Category | Amount (₺) | Variance |\n|---|---|---|\n| Revenue | 150,000 | +12% |\n| COGS | -45,000 | -2% |\n| **Gross Profit** | **105,000** | **+19%** |\n\nOverall margin has improved compared to last quarter.'
      } else if (currentMode === 'tax') {
        aiResponse = '⚠️ **Risk Detected**: Deductions claimed under generic "Office Supplies" exceed standard thresholds by 35%.\n\n*Recommendation*: Re-categorize high-value items as depreciable assets according to VUK Code 315.'
      } else if (currentMode === 'legislation') {
        aiResponse = 'According to the **Official Gazette No. 32050**, the standard corporate tax rate has been adjusted to 25% for general companies, effective from the next fiscal year. Exemptions apply to export-oriented revenues.'
      } else {
        aiResponse = 'Document inspection complete. All required signatures are present and the invoice totals align mathematically. No anomalies detected.'
      }

      setMessages(prev => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: aiResponse
        }
      ])
      setIsProcessing(false)
    }, 2000)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full bg-zinc-950 rounded-2xl shadow-sm border border-zinc-800 overflow-hidden">
      {/* Header Area */}
      <div className="px-6 py-4 border-b border-zinc-800 bg-zinc-950/70 backdrop-blur-md z-10 sticky top-0">
        <h2 className="text-xl font-semibold text-zinc-100 mb-4">Çalışma Alanı</h2>
        <ModeSelector currentMode={currentMode} onModeChange={setCurrentMode} />
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-zinc-950">
        {messages.map((msg) => (
          <div key={msg.id} className={cn("flex gap-4 max-w-4xl mx-auto", msg.role === 'user' ? "flex-row-reverse" : "flex-row")}>
            {/* Avatar */}
            <div className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1",
              msg.role === 'user' ? "bg-zinc-800 text-white" : "bg-zinc-100 text-zinc-900"
            )}>
              {msg.role === 'user' ? <UserIcon size={16} /> : <Bot size={16} />}
            </div>
            
            {/* Message Bubble */}
            <div className={cn(
              "flex flex-col gap-2 max-w-[80%]",
              msg.role === 'user' ? "items-end" : "items-start"
            )}>
              {msg.file && (
                <div className="flex items-center gap-2 bg-zinc-800 border border-zinc-700 text-zinc-300 px-3 py-2 rounded-lg text-sm">
                  <Paperclip size={14} className="text-zinc-500" />
                  {msg.file.name}
                </div>
              )}
              
              {msg.content && (
                <div className={cn(
                  "px-5 py-3.5 rounded-2xl text-[15px] leading-relaxed shadow-sm",
                  msg.role === 'user' 
                    ? "bg-zinc-800 text-zinc-200 rounded-tr-sm" 
                    : "bg-zinc-900 border border-zinc-800 text-zinc-300 rounded-tl-sm prose prose-sm prose-invert max-w-none prose-p:leading-relaxed prose-th:text-left prose-th:bg-zinc-800 prose-td:border-t prose-td:border-zinc-800 prose-table:border prose-table:border-zinc-700 prose-table:rounded-lg overflow-hidden"
                )}>
                  {msg.role === 'user' ? (
                    <span className="whitespace-pre-wrap">{msg.content}</span>
                  ) : (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Processing State */}
        {isProcessing && (
          <div className="flex gap-4 max-w-4xl mx-auto">
            <div className="w-8 h-8 rounded-full bg-zinc-100 text-zinc-900 flex items-center justify-center shrink-0 mt-1 shadow-md">
              <Bot size={16} />
            </div>
            <div className="flex items-center gap-3 px-5 py-3.5 bg-zinc-900 border border-zinc-800 rounded-2xl rounded-tl-sm shadow-sm text-zinc-400 text-sm">
              <Loader2 size={16} className="animate-spin text-zinc-300" />
              <span>Veriler analiz ediliyor...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-zinc-950 border-t border-zinc-800 backdrop-blur-md">
        <div className="max-w-4xl mx-auto">
          {showUpload && (
            <FileUploadZone 
              selectedFile={selectedFile} 
              onFileSelect={(file) => setSelectedFile(file)}
              onClearFile={() => setSelectedFile(null)}
            />
          )}
          
          <div className="relative flex items-end gap-2 bg-zinc-900 border border-zinc-700 rounded-3xl shadow-sm focus-within:border-zinc-500 transition-colors p-2">
            <button 
              onClick={() => setShowUpload(!showUpload)}
              className={cn(
                "p-2.5 rounded-full transition-colors shrink-0",
                showUpload || selectedFile ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-300"
              )}
              title="Upload Document"
            >
              <Paperclip size={20} />
            </button>
            
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Finansal verileri yapıştırın veya rapor isteyin..."
              className="w-full max-h-32 min-h-[44px] py-2.5 px-2 pr-12 bg-transparent border-none focus:outline-none focus:ring-0 resize-none text-[15px] text-zinc-200 placeholder:text-zinc-500"
              rows={1}
              style={{ height: input ? 'auto' : '44px' }}
            />
            
            <button
              onClick={handleSend}
              disabled={!input.trim() && !selectedFile || isProcessing}
              className="absolute right-2 bottom-2 p-2 bg-zinc-100 text-zinc-950 rounded-full hover:bg-white disabled:opacity-50 disabled:bg-zinc-800 disabled:text-zinc-500 transition-colors shadow-sm"
            >
              <ArrowUp size={18} className={cn(isProcessing && "animate-pulse")} />
            </button>
          </div>
          <div className="text-center mt-2">
            <span className="text-xs text-zinc-500">FinAI hata yapabilir. Önemli finansal verileri doğrulayın.</span>
          </div>
        </div>
      </div>
    </div>
  )
}
