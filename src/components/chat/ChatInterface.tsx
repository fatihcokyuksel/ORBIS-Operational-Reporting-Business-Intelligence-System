"use client"

import React, { useState, useRef, useEffect } from 'react'
import { ModeSelector, type ActionMode } from './ModeSelector'
import { FileUploadZone } from './FileUploadZone'
import { User as UserIcon, Bot, Loader2, Paperclip, ArrowUp, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useSearchParams, useRouter } from 'next/navigation'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  file?: File | null
}

const MAX_CHARS = 5000

export function ChatInterface() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const chatIdFromUrl = searchParams.get('chat')

  const [currentMode, setCurrentMode] = useState<ActionMode>('revenue')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [showUpload, setShowUpload] = useState(false)
  const [chatId, setChatId] = useState<string | null>(null)
  const [loadingChat, setLoadingChat] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // When URL changes (?chat=xxx), load that chat's messages
  useEffect(() => {
    if (chatIdFromUrl) {
      setChatId(chatIdFromUrl)
      loadChatMessages(chatIdFromUrl)
    } else {
      // No chat in URL = fresh empty state
      setChatId(null)
      setMessages([])
    }
  }, [chatIdFromUrl])

  async function loadChatMessages(id: string) {
    setLoadingChat(true)
    try {
      const res = await fetch(`/api/chats/${id}/messages`)
      if (res.ok) {
        const data = await res.json()
        setMessages(data.map((m: any) => ({
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content: m.content,
        })))
      }
    } catch (err) {
      console.error('Failed to load chat:', err)
    } finally {
      setLoadingChat(false)
    }
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isProcessing])

  // Auto-resize textarea, enforcing char limit
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value
    if (value.length > MAX_CHARS) return
    setInput(value)
    const ta = e.target
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
  }

  const atLimit = input.length >= MAX_CHARS

  const handleSend = async () => {
    if ((!input.trim() && !selectedFile) || atLimit) return

    const userText = input
    const fileRef = selectedFile
    setInput('')
    setSelectedFile(null)
    setShowUpload(false)

    if (textareaRef.current) {
      textareaRef.current.style.height = '36px'
    }

    setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', content: userText, file: fileRef }])
    setIsProcessing(true)

    try {
      let currentChatId = chatId

      // Create new chat session if needed
      if (!currentChatId) {
        const chatRes = await fetch('/api/chats', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: userText.substring(0, 40) }),
        })
        const newChat = await chatRes.json()
        currentChatId = newChat.id
        setChatId(currentChatId)
        // Navigate to URL with chat param so sidebar picks it up
        router.push(`/?chat=${currentChatId}`, { scroll: false })

        // The greeting was inserted by the API; load it into our messages at the front
        const greetingRes = await fetch(`/api/chats/${currentChatId}/messages`)
        if (greetingRes.ok) {
          const greetingMsgs = await greetingRes.json()
          setMessages(prev => {
            const greetings = greetingMsgs.map((m: any) => ({
              id: m.id,
              role: m.role as 'user' | 'assistant',
              content: m.content,
            }))
            // Put greeting before the user msg we already added
            return [...greetings, ...prev.filter(m => m.role === 'user')]
          })
        }
      }

      // Save user message to DB
      if (currentChatId) {
        await fetch(`/api/chats/${currentChatId}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role: 'user', content: userText }),
        })
      }

      // Simulate AI response (replace with real LLM call later)
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

      // Save AI response to DB
      if (currentChatId) {
        await fetch(`/api/chats/${currentChatId}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role: 'assistant', content: aiResponse }),
        })
      }

      setMessages(prev => [...prev, { id: (Date.now() + 1).toString(), role: 'assistant', content: aiResponse }])
    } catch (error) {
      console.error(error)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div className="flex flex-col h-full bg-zinc-950">
      {/* Mode Selector */}
      <div className="shrink-0 px-6 pt-5 pb-3 border-b border-zinc-800/60">
        <ModeSelector currentMode={currentMode} onModeChange={setCurrentMode} />
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        {loadingChat ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
          </div>
        ) : isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full gap-4 px-4 text-center">
            <div className="w-14 h-14 rounded-2xl bg-zinc-800 flex items-center justify-center">
              <Sparkles className="w-7 h-7 text-zinc-300" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-zinc-100 mb-1">FatihGPT</h2>
              <p className="text-zinc-500 text-sm max-w-sm">
                Select a mode above and describe your request, or upload a financial document to begin.
              </p>
            </div>
          </div>
        ) : (
          <div className="py-8 space-y-8 max-w-3xl mx-auto px-4 w-full">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  "flex gap-3 w-full animate-in fade-in slide-in-from-bottom-2 duration-300",
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
                  {msg.file && (
                    <div className="flex items-center gap-2 bg-zinc-800 border border-zinc-700 text-zinc-300 px-3 py-1.5 rounded-lg text-sm">
                      <Paperclip size={12} className="text-zinc-500 shrink-0" />
                      <span className="truncate">{msg.file.name}</span>
                    </div>
                  )}
                  {msg.content && (
                    <div className={cn(
                      "text-[15px] leading-7",
                      msg.role === 'user'
                        ? "bg-zinc-800 text-zinc-100 px-4 py-2.5 rounded-2xl rounded-tr-md [word-break:break-word] [overflow-wrap:anywhere] whitespace-pre-wrap"
                        : "text-zinc-200 w-full [word-break:break-word] [overflow-wrap:anywhere] prose prose-sm prose-invert max-w-none prose-p:leading-7 prose-p:my-2 prose-headings:text-zinc-100 prose-th:text-left prose-table:w-full prose-code:text-zinc-300 prose-code:bg-zinc-800 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-pre:bg-zinc-900 prose-pre:border prose-pre:border-zinc-800 prose-pre:overflow-x-auto"
                    )}>
                      {msg.role === 'user' ? (
                        msg.content
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

            {isProcessing && (
              <div className="flex gap-3 animate-in fade-in duration-300">
                <div className="w-7 h-7 rounded-full bg-white text-zinc-900 flex items-center justify-center shrink-0 mt-0.5">
                  <Bot size={13} />
                </div>
                <div className="flex items-center gap-1.5 px-4 py-3">
                  <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="shrink-0 px-4 pb-5 pt-3">
        <div className="max-w-3xl mx-auto w-full">
          {showUpload && (
            <div className="mb-3">
              <FileUploadZone
                selectedFile={selectedFile}
                onFileSelect={(file) => setSelectedFile(file)}
                onClearFile={() => setSelectedFile(null)}
              />
            </div>
          )}

          <div className="flex items-end gap-2 bg-zinc-900 border border-zinc-800 rounded-2xl focus-within:border-zinc-700 transition-colors duration-200 px-2 py-2">
            <button
              onClick={() => setShowUpload(!showUpload)}
              className={cn(
                "shrink-0 w-9 h-9 flex items-center justify-center rounded-xl transition-all duration-150",
                showUpload || selectedFile
                  ? "text-zinc-200 bg-zinc-700"
                  : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
              )}
              title="Attach file"
            >
              <Paperclip size={17} />
            </button>

            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Paste financial data or describe your request…"
              className="flex-1 bg-transparent border-none focus:outline-none focus:ring-0 resize-none text-[15px] text-zinc-200 placeholder:text-zinc-500 min-h-[36px] max-h-[200px] leading-[1.6] overflow-y-auto py-1.5 align-middle"
              rows={1}
              style={{ height: '36px' }}
            />

            <button
              onClick={handleSend}
              disabled={(!input.trim() && !selectedFile) || isProcessing || atLimit}
              className="shrink-0 w-9 h-9 flex items-center justify-center bg-white text-zinc-900 rounded-xl hover:bg-zinc-100 disabled:opacity-25 disabled:cursor-not-allowed transition-all duration-150"
            >
              {isProcessing
                ? <Loader2 size={15} className="animate-spin" />
                : <ArrowUp size={15} />
              }
            </button>
          </div>

          {/* Character count + disclaimer */}
          <div className="relative flex items-center justify-center mt-2 px-1">
            <p className="text-xs text-zinc-600 text-center">
              FatihGPT can make mistakes. Verify important financial data.
            </p>
            {input.length > 0 && (
              <p className={cn(
                "absolute right-1 text-xs tabular-nums transition-colors",
                atLimit ? "text-red-400" : input.length > MAX_CHARS * 0.9 ? "text-yellow-500" : "text-zinc-600"
              )}>
                {input.length.toLocaleString()} / {MAX_CHARS.toLocaleString()}
              </p>
            )}
          </div>
          {atLimit && (
            <p className="text-xs text-red-400 text-center mt-1">
              Maximum {MAX_CHARS.toLocaleString()} characters reached
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
