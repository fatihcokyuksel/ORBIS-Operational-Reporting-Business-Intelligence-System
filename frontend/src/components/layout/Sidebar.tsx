"use client"

import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  MessageSquare, PlusCircle, User, LogOut,
  PanelLeftClose, PanelLeftOpen, MoreHorizontal,
  Pin, PinOff, Trash2, Menu, X, Bot, FileText
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'

interface ChatItem {
  id: string
  title: string
  isPinned: boolean
  updatedAt: string
}

interface SessionUser {
  id: string
  name?: string | null
  email?: string | null
}

interface SessionResponse {
  user: SessionUser | null
  reason?: string
}

export function Sidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [isMobileOpen, setIsMobileOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()
  const activeChatId = searchParams.get('chat')

  const [chatHistory, setChatHistory] = useState<ChatItem[]>([])
  const [user, setUser] = useState<SessionUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const isAuthPage = pathname === '/login' || pathname === '/signin' || pathname === '/signup'

  // Detect mobile viewport
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)')
    const handleChange = (e: MediaQueryListEvent | MediaQueryList) => {
      setIsMobile(e.matches)
      if (e.matches) {
        setIsMobileOpen(false)
      }
    }
    handleChange(mq)
    mq.addEventListener('change', handleChange)
    return () => mq.removeEventListener('change', handleChange)
  }, [])

  // Close mobile sidebar on navigation
  useEffect(() => {
    if (isMobile) {
      queueMicrotask(() => setIsMobileOpen(false))
    }
  }, [pathname, activeChatId, isMobile])

  // Prevent body scroll when mobile sidebar is open
  useEffect(() => {
    if (isMobile && isMobileOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [isMobile, isMobileOpen])

  const fetchChats = useCallback(async () => {
    try {
      const res = await fetch('/api/chats', { cache: 'no-store' })
      if (res.status === 401) {
        setUser(null)
        setChatHistory([])
        await fetch('/api/auth/logout', { method: 'POST' }).catch(() => undefined)
        router.replace('/login')
        router.refresh()
        return
      }
      const data = await res.json()
      if (Array.isArray(data)) setChatHistory(data)
    } catch {}
  }, [router])

  const fetchSession = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/auth/session', { cache: 'no-store' })
      const data = await res.json() as SessionResponse
      if (data.user) {
        setUser(data.user)
        await fetchChats()
      } else {
        setUser(null)
        setChatHistory([])
        if (!isAuthPage) {
          await fetch('/api/auth/logout', { method: 'POST' }).catch(() => undefined)
          router.replace('/login')
          router.refresh()
        }
      }
    } catch (error) {
      console.error(error)
      setUser(null)
      setChatHistory([])
    } finally {
      setLoading(false)
    }
  }, [fetchChats, isAuthPage, router])

  useEffect(() => {
    queueMicrotask(() => {
      if (isAuthPage) {
        setUser(null)
        setChatHistory([])
        setLoading(false)
        return
      }

      void fetchSession()
    })
  }, [isAuthPage, fetchSession])

  useEffect(() => {
    if (!user) return
    queueMicrotask(() => void fetchChats())
  }, [activeChatId, pathname, user, fetchChats])

  // Close menu on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleLogout = async () => {
    setUser(null)
    setChatHistory([])
    await fetch('/api/auth/logout', { method: 'POST' })
    router.push('/login')
    router.refresh()
  }

  const handleNewChat = () => {
    router.push('/')
  }

  const handleSelectChat = (chatId: string) => {
    router.push(`/?chat=${chatId}`)
  }

  const handleDeleteChat = async (chatId: string) => {
    await fetch(`/api/chats/${chatId}`, { method: 'DELETE' })
    setChatHistory(prev => prev.filter(c => c.id !== chatId))
    setMenuOpenId(null)
    // If the deleted chat is currently open, go to empty state
    if (activeChatId === chatId) {
      router.push('/')
    }
  }

  const handleTogglePin = async (chat: ChatItem) => {
    const newPinned = !chat.isPinned
    await fetch(`/api/chats/${chat.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ isPinned: newPinned }),
    })
    // Update local state and re-sort
    setChatHistory(prev => {
      const updated = prev.map(c => c.id === chat.id ? { ...c, isPinned: newPinned } : c)
      return updated.sort((a, b) => {
        if (a.isPinned !== b.isPinned) return a.isPinned ? -1 : 1
        return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
      })
    })
    setMenuOpenId(null)
  }

  if (isAuthPage) return null

  const pinnedChats = chatHistory.filter(c => c.isPinned)
  const recentChats = chatHistory.filter(c => !c.isPinned)

  // On mobile, show the sidebar as collapsed by default in the aside
  const showCollapsed = isMobile ? false : isCollapsed

  const sidebarContent = (
    <aside className={cn(
      "relative flex flex-col h-screen bg-zinc-900 border-r border-zinc-800 transition-all duration-300 ease-in-out",
      isMobile
        ? "w-[280px]"
        : isCollapsed ? "w-[60px]" : "w-[260px]"
    )}>

      {/* Header */}
      <div className={cn(
        "flex items-center h-14 border-b border-zinc-800 px-3 shrink-0 gap-2.5",
        showCollapsed && "justify-center"
      )}>
        <div className="w-7 h-7 flex items-center justify-center shrink-0">
          <Bot size={24} className="text-white" />
        </div>
        {!showCollapsed && (
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-sm text-white leading-tight truncate">ORBIS</p>
            <p className="text-xs text-zinc-500 truncate">Yapay Zeka Finans Asistanı</p>
          </div>
        )}
        {!showCollapsed && (
          <button
            onClick={() => isMobile ? setIsMobileOpen(false) : setIsCollapsed(true)}
            className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-all duration-150"
            title={isMobile ? "Menüyü kapat" : "Yan menüyü daralt"}
          >
            {isMobile ? <X size={16} /> : <PanelLeftClose size={16} />}
          </button>
        )}
      </div>

      {/* Expand button when collapsed (desktop only) */}
      {!isMobile && isCollapsed && (
        <button
          onClick={() => setIsCollapsed(false)}
          className="mt-3 mx-auto p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-all duration-150"
          title="Yan menüyü genişlet"
        >
          <PanelLeftOpen size={16} />
        </button>
      )}

      {/* Yeni sohbet butonu */}
      <div className="px-3 pt-3 pb-1 shrink-0">
        <button
          onClick={handleNewChat}
          className={cn(
            "w-full flex items-center gap-2.5 rounded-lg hover:bg-zinc-700 text-zinc-200 transition-all duration-150 group",
            showCollapsed ? "justify-center p-2" : "px-3 py-2",
            pathname === '/' && !activeChatId ? "bg-zinc-800" : "bg-transparent"
          )}
        >
          <PlusCircle size={16} className="shrink-0 text-zinc-400 group-hover:text-zinc-200 transition-colors" />
          {!showCollapsed && <span className="text-sm font-medium">Yeni sohbet</span>}
        </button>
      </div>

      {/* Raporlarım butonu */}
      <div className="px-3 pt-1 pb-1 shrink-0">
        <Link
          href="/reports"
          className={cn(
            "w-full flex items-center gap-2.5 rounded-lg hover:bg-zinc-800 text-zinc-200 transition-all duration-150 group",
            showCollapsed ? "justify-center p-2" : "px-3 py-2",
            pathname === '/reports' ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"
          )}
        >
          <FileText size={16} className="shrink-0 text-zinc-400 group-hover:text-zinc-200 transition-colors" />
          {!showCollapsed && <span className="text-sm font-medium">Raporlarım</span>}
        </Link>
      </div>

      {/* Chat History */}
      <div className="sidebar-scroll flex-1 overflow-y-auto px-3 py-2 space-y-0.5">
        {loading && !showCollapsed && (
          <p className="text-xs text-zinc-600 px-2 py-1">Yükleniyor...</p>
        )}

        {user && chatHistory.length === 0 && !showCollapsed && !loading && (
          <p className="text-xs text-zinc-600 px-2 py-1">Henüz sohbet yok</p>
        )}

        {/* Pinned section */}
        {!showCollapsed && pinnedChats.length > 0 && (
          <p className="text-[11px] font-semibold text-zinc-600 uppercase tracking-wider px-2 pb-1 pt-2">
            <Pin size={10} className="inline mr-1 -mt-0.5" />
            Sabitlenenler
          </p>
        )}
        {pinnedChats.map(chat => renderChatItem(chat))}

        {/* Recent section */}
        {!showCollapsed && recentChats.length > 0 && (
          <p className="text-[11px] font-semibold text-zinc-600 uppercase tracking-wider px-2 pb-1 pt-2">Son sohbetler</p>
        )}
        {recentChats.map(chat => renderChatItem(chat))}
      </div>

      {/* Footer */}
      <div className="shrink-0 border-t border-zinc-800 p-3 space-y-0.5">
        {user ? (
          <>
            <div className={cn(
              "flex items-center gap-2.5 px-2 py-1.5 rounded-lg",
              showCollapsed && "justify-center"
            )}>
              <div className="w-6 h-6 rounded-full bg-zinc-700 flex items-center justify-center shrink-0">
                <User size={12} className="text-zinc-300" />
              </div>
              {!showCollapsed && (
                <span className="text-xs text-zinc-500 truncate flex-1">{user.name || 'Kullanıcı'}</span>
              )}
            </div>
            <button
              onClick={handleLogout}
              className={cn(
                "w-full flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-red-500/10 transition-all duration-150 group",
                showCollapsed && "justify-center"
              )}
            >
              <LogOut size={14} className="text-zinc-600 group-hover:text-red-400 transition-colors shrink-0" />
              {!showCollapsed && (
                <span className="text-sm text-zinc-500 group-hover:text-red-400 transition-colors">Çıkış yap</span>
              )}
            </button>
          </>
        ) : (
          <Link
            href="/signin"
            className={cn(
              "flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-zinc-800 transition-all duration-150 group",
              showCollapsed && "justify-center"
            )}
          >
            <User size={14} className="text-zinc-600 group-hover:text-zinc-300 transition-colors shrink-0" />
            {!showCollapsed && (
              <span className="text-sm text-zinc-500 group-hover:text-zinc-200 transition-colors">Giriş yap</span>
            )}
          </Link>
        )}
      </div>
    </aside>
  )

  // Mobile: floating hamburger + overlay sidebar
  if (isMobile) {
    return (
      <>
        {/* Floating hamburger button - visible when sidebar is closed */}
        {!isMobileOpen && (
          <button
            onClick={() => setIsMobileOpen(true)}
            className="fixed top-3 left-3 z-40 w-10 h-10 flex items-center justify-center rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 transition-all duration-150 shadow-lg"
            aria-label="Menüyü aç"
          >
            <Menu size={20} />
          </button>
        )}

        {/* Backdrop */}
        {isMobileOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
            onClick={() => setIsMobileOpen(false)}
          />
        )}

        {/* Sidebar drawer */}
        <div className={cn(
          "fixed inset-y-0 left-0 z-50 transition-transform duration-300 ease-in-out",
          isMobileOpen ? "translate-x-0" : "-translate-x-full"
        )}>
          {sidebarContent}
        </div>
      </>
    )
  }

  // Desktop: normal inline sidebar
  return sidebarContent

  function renderChatItem(chat: ChatItem) {
    const isActive = activeChatId === chat.id
    const isMenuOpen = menuOpenId === chat.id

    return (
      <div key={chat.id} className="relative group">
        <button
          onClick={() => handleSelectChat(chat.id)}
          className={cn(
            "w-full flex items-center gap-2.5 px-2 py-1.5 rounded-lg transition-all duration-150 text-left",
            showCollapsed && "justify-center",
            isActive
              ? "bg-zinc-800 text-zinc-100"
              : "hover:bg-zinc-800/60 text-zinc-400 hover:text-zinc-200"
          )}
        >
          <MessageSquare size={14} className="shrink-0 transition-colors" />
          {!showCollapsed && (
            <span className="text-sm truncate flex-1">{chat.title}</span>
          )}
          {!showCollapsed && chat.isPinned && (
            <Pin size={11} className="text-zinc-600 shrink-0" />
          )}
        </button>

        {/* Three-dot menu trigger */}
        {!showCollapsed && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              setMenuOpenId(isMenuOpen ? null : chat.id)
            }}
            className={cn(
              "absolute right-1 top-1/2 -translate-y-1/2 p-1 rounded-md transition-all duration-150",
              isMenuOpen
                ? "opacity-100 bg-zinc-700 text-zinc-200"
                : "opacity-0 group-hover:opacity-100 text-zinc-600 hover:text-zinc-300 hover:bg-zinc-700",
              // On mobile, always show the menu trigger for touch accessibility
              isMobile && "opacity-100"
            )}
          >
            <MoreHorizontal size={14} />
          </button>
        )}

        {/* Dropdown menu */}
        {isMenuOpen && (
          <div
            ref={menuRef}
            className="absolute right-0 top-full mt-1 z-50 w-40 bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl py-1 animate-in fade-in slide-in-from-top-1 duration-150"
          >
            <button
              onClick={(e) => {
                e.stopPropagation()
                handleTogglePin(chat)
              }}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors"
            >
              {chat.isPinned ? (
                <>
                  <PinOff size={13} />
                  <span>Sabitlemeyi kaldır</span>
                </>
              ) : (
                <>
                  <Pin size={13} />
                  <span>Sohbeti sabitle</span>
                </>
              )}
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation()
                handleDeleteChat(chat.id)
              }}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-colors"
            >
              <Trash2 size={13} />
              <span>Sohbeti sil</span>
            </button>
          </div>
        )}
      </div>
    )
  }
}
