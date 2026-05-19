"use client"

import { useCallback, useEffect, useRef, useState } from 'react'
import { Bot, Loader2 } from 'lucide-react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ChatInput } from './ChatInput'
import { MessageItem, type Message } from './MessageItem'
import { ModeSelector, type ActionMode } from './ModeSelector'
import { getArtifactModeInfo, isArtifactModeValue } from './modeCatalog'

interface ApiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  fileName?: string
}

class UnauthorizedSessionError extends Error {}

const DRAFT_MODE_KEY = 'artifact-mode:draft'

async function readApiError(res: Response, fallback: string) {
  const contentType = res.headers.get('content-type') || ''
  try {
    if (contentType.includes('application/json')) {
      const data = await res.json() as { message?: unknown; detail?: unknown }
      if (typeof data.message === 'string' && data.message.trim()) return data.message
      if (typeof data.detail === 'string' && data.detail.trim()) return data.detail
      if (data.detail && typeof data.detail === 'object' && 'message' in data.detail && typeof data.detail.message === 'string' && data.detail.message.trim()) {
        return data.detail.message
      }
    } else {
      const text = await res.text()
      if (text.trim() && !text.trimStart().startsWith('<')) return text
    }
  } catch (error) {
    console.error('API hata cevabi okunamadi:', error)
  }
  return fallback
}

function storageKeyForChat(chatId: string | null) {
  return chatId ? `artifact-mode:${chatId}` : DRAFT_MODE_KEY
}

export function ChatInterface() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const chatIdFromUrl = searchParams.get('chat')
  const artifactFromUrl = searchParams.get('artifact')

  const [currentMode, setCurrentMode] = useState<ActionMode>('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [chatId, setChatId] = useState<string | null>(null)
  const [loadingChat, setLoadingChat] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const prevChatIdRef = useRef<string | null | undefined>(undefined)
  const selectedArtifactInfo = getArtifactModeInfo(currentMode)

  const redirectToLogin = useCallback(async () => {
    await fetch('/api/auth/logout', { method: 'POST' }).catch(() => undefined)
    router.replace('/login')
    router.refresh()
  }, [router])

  const persistMode = useCallback((mode: string, targetChatId: string | null) => {
    const storageKey = storageKeyForChat(targetChatId)
    if (mode) {
      window.localStorage.setItem(storageKey, mode)
    } else {
      window.localStorage.removeItem(storageKey)
    }
    const params = new URLSearchParams(searchParams.toString())
    if (mode) params.set('artifact', mode)
    else params.delete('artifact')
    const query = params.toString()
    router.replace(query ? `/?${query}` : '/', { scroll: false })
  }, [router, searchParams])

  const handleModeChange = useCallback((mode: ActionMode) => {
    setCurrentMode(mode)
    persistMode(mode, chatId ?? chatIdFromUrl)
  }, [chatId, chatIdFromUrl, persistMode])

  const loadChatMessages = useCallback(async (id: string) => {
    setLoadingChat(true)
    try {
      const res = await fetch(`/api/chats/${id}/messages`)
      if (res.status === 401) {
        await redirectToLogin()
        return
      }
      if (res.ok) {
        const data = await res.json() as ApiMessage[]
        setMessages(data.map((message) => ({
          id: message.id,
          role: message.role,
          content: message.content,
          fileName: message.fileName,
        })))
      }
    } catch (error) {
      console.error('Sohbet yuklenemedi:', error)
    } finally {
      setLoadingChat(false)
    }
  }, [redirectToLogin])

  useEffect(() => {
    queueMicrotask(() => {
      if (chatIdFromUrl !== prevChatIdRef.current) {
        prevChatIdRef.current = chatIdFromUrl || null
        setIsProcessing(false)
        if (chatIdFromUrl) {
          setChatId(chatIdFromUrl)
          void loadChatMessages(chatIdFromUrl)
        } else {
          setChatId(null)
          setMessages([])
        }
      }
    })
  }, [chatIdFromUrl, loadChatMessages])

  useEffect(() => {
    if (artifactFromUrl && isArtifactModeValue(artifactFromUrl)) {
      setCurrentMode(artifactFromUrl)
      return
    }
    const storedMode = window.localStorage.getItem(storageKeyForChat(chatIdFromUrl))
    if (storedMode && isArtifactModeValue(storedMode)) {
      setCurrentMode(storedMode)
    } else if (!artifactFromUrl) {
      setCurrentMode('')
    }
  }, [artifactFromUrl, chatIdFromUrl])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isProcessing])

  const handleSend = async (userText: string, fileRefs: File[]) => {
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now().toString(),
        role: 'user',
        content: userText,
        files: fileRefs,
      },
    ])
    setIsProcessing(true)

    let currentChatId = chatId

    const canUpdateCurrentChat = () => !currentChatId || prevChatIdRef.current === currentChatId
    const appendAssistantMessage = (content: string) => {
      if (!canUpdateCurrentChat()) return
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content,
          isStreaming: false,
        },
      ])
    }

    const createChatSession = async () => {
      const chatRes = await fetch('/api/chats', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: userText.substring(0, 40) || 'Yeni Artifact Sohbeti' }),
      })

      if (chatRes.status === 401) {
        await redirectToLogin()
        throw new UnauthorizedSessionError()
      }
      if (!chatRes.ok) {
        throw new Error(await readApiError(chatRes, 'Sohbet olusturulamadi. Lutfen tekrar deneyin.'))
      }

      const newChat = await chatRes.json() as { id?: string }
      if (!newChat.id) {
        throw new Error('Sohbet olusturulamadi. Lutfen tekrar deneyin.')
      }

      setChatId(newChat.id)
      prevChatIdRef.current = newChat.id
      const params = new URLSearchParams(searchParams.toString())
      params.delete('artifact')
      params.set('chat', newChat.id)
      router.push(`/?${params.toString()}`, { scroll: false })
      return newChat.id
    }

    const isArtifactMode = isArtifactModeValue(currentMode)
    if (isArtifactMode) {
      const submittedMode = currentMode
      handleModeChange('')

      try {
        if (!currentChatId) {
          currentChatId = await createChatSession()
        }

        const artifactInfo = getArtifactModeInfo(submittedMode)
        if (!artifactInfo) {
          throw new Error('Secilen uretim modu bulunamadi.')
        }

        const formData = new FormData()
        formData.append('artifactType', artifactInfo.artifactType)
        formData.append('artifactId', submittedMode)
        if (artifactInfo.artifactType === 'report') formData.append('reportType', submittedMode)
        fileRefs.forEach((file) => formData.append('files', file))
        if (currentChatId) formData.append('conversationId', currentChatId)
        if (userText) formData.append('userPrompt', userText)

        const res = await fetch('/api/reports/generate', {
          method: 'POST',
          body: formData,
        })

        if (res.status === 401) {
          await redirectToLogin()
          throw new UnauthorizedSessionError()
        }
        if (!res.ok) {
          throw new Error(await readApiError(res, 'Artifact olusturulurken bir hata olustu. Lutfen tekrar deneyin.'))
        }

        const assistantMsg = await res.json() as ApiMessage
        if (canUpdateCurrentChat()) {
          setMessages((prev) => [
            ...prev,
            {
              id: assistantMsg.id,
              role: 'assistant',
              content: assistantMsg.content,
              isStreaming: false,
            },
          ])
        }
      } catch (error) {
        console.error(error)
        if (error instanceof UnauthorizedSessionError) return
        const message = error instanceof Error && error.message.trim()
          ? error.message
          : 'Sunucuya baglanilamadi. Lutfen baglantinizi kontrol edin.'
        appendAssistantMessage(message)
      } finally {
        if (canUpdateCurrentChat()) setIsProcessing(false)
      }
      return
    }

    try {
      if (!currentChatId) {
        currentChatId = await createChatSession()
      }

      const firstFile = fileRefs[0]
      let fileData: { name: string; type: string; data: string } | undefined
      if (firstFile) {
        const base64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => resolve(reader.result as string)
          reader.onerror = () => reject(new Error('Dosya okunamadi. Lutfen tekrar deneyin.'))
          reader.readAsDataURL(firstFile)
        })
        fileData = {
          name: firstFile.name,
          type: firstFile.type,
          data: base64,
        }
      }

      const sendMessage = (targetChatId: string) => fetch(`/api/chats/${targetChatId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: 'user', content: userText, file: fileData, mode: currentMode }),
      })

      let res = await sendMessage(currentChatId)
      if (res.status === 404) {
        currentChatId = await createChatSession()
        res = await sendMessage(currentChatId)
      }
      if (res.status === 401) {
        await redirectToLogin()
        throw new UnauthorizedSessionError()
      }
      if (!res.ok) {
        throw new Error(await readApiError(res, 'Bir hata olustu. Lutfen tekrar deneyin.'))
      }

      const assistantMsg = await res.json() as ApiMessage
      if (canUpdateCurrentChat()) {
        setMessages((prev) => [
          ...prev,
          {
            id: assistantMsg.id,
            role: 'assistant',
            content: assistantMsg.content,
            isStreaming: true,
          },
        ])
      }
    } catch (error) {
      console.error(error)
      if (error instanceof UnauthorizedSessionError) return
      const message = error instanceof Error && error.message.trim()
        ? error.message
        : 'Sunucuya baglanilamadi. Lutfen baglantinizi kontrol edin.'
      appendAssistantMessage(message)
    } finally {
      if (canUpdateCurrentChat()) setIsProcessing(false)
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div className="flex flex-col h-full bg-zinc-950 overflow-hidden">
      <div className="shrink-0 px-3 sm:px-6 pt-16 sm:pt-5 pb-3 border-b border-zinc-800/60">
        <ModeSelector currentMode={currentMode} onModeChange={handleModeChange} />
      </div>

      <div className="flex-1 overflow-y-auto">
        {loadingChat ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
          </div>
        ) : isEmpty ? (
          isArtifactModeValue(currentMode) ? null : (
            <div className="flex flex-col items-center justify-center h-full gap-3 sm:gap-4 px-4 text-center">
              <div className="w-12 h-12 sm:w-14 sm:h-14 flex items-center justify-center mb-2">
                <Bot className="w-10 h-10 sm:w-12 sm:h-12 text-white" />
              </div>
              <div>
                <h2 className="text-lg sm:text-xl font-semibold text-zinc-100 mb-1">ORBIS</h2>
                <p className="text-zinc-500 text-xs sm:text-sm max-w-sm">
                  Yukaridan bir islem secip isteginizi yazin veya finansal bir belge yukleyerek baslayin.
                </p>
              </div>
            </div>
          )
        ) : (
          <div className="py-4 sm:py-8 space-y-6 sm:space-y-8 max-w-3xl mx-auto px-3 sm:px-4 w-full">
            {messages.map((msg) => (
              <MessageItem
                key={msg.id}
                msg={msg}
                onTick={() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' })}
                onDone={(id) => {
                  setMessages((prev) => prev.map((item) => (
                    item.id === id ? { ...item, isStreaming: false } : item
                  )))
                }}
              />
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

      <ChatInput onSend={handleSend} isProcessing={isProcessing} currentMode={currentMode} />
    </div>
  )
}
