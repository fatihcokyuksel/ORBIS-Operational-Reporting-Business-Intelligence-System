"use client"

import React, { useState, useEffect, useRef } from 'react'
import {
  MessageSquare, PlusCircle, User, FileText, LogOut,
  PanelLeftClose, PanelLeftOpen, MoreHorizontal,
  Pin, PinOff, Trash2
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

export function Sidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()
  const activeChatId = searchParams.get('chat')

  const [chatHistory, setChatHistory] = useState<ChatItem[]>([])
  const [user, setUser] = useState<{ email: string } | null>(null)
  const [loading, setLoading] = useState(true)
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const fetchChats = async () => {
    try {
      const res = await fetch('/api/chats')
      const data = await res.json()
      if (Array.isArray(data)) setChatHistory(data)
    } catch {}
  }

  useEffect(() => {
    fetch('/api/auth/session')
      .then(res => res.json())
      .then(data => {
        if (data.user) {
          setUser(data.user)
          fetchChats()
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  // Re-fetch chats when pathname changes (e.g. after navigation)
  useEffect(() => {
    if (user) fetchChats()
  }, [pathname, searchParams])

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

  if (pathname === '/login' || pathname === '/signup') return null

  const pinnedChats = chatHistory.filter(c => c.isPinned)
  const recentChats = chatHistory.filter(c => !c.isPinned)

  return (
    <aside className={cn(
      "relative flex flex-col h-screen bg-zinc-900 border-r border-zinc-800 transition-all duration-300 ease-in-out",
      isCollapsed ? "w-[60px]" : "w-[260px]"
    )}>

      {/* Header */}
      <div className={cn(
        "flex items-center h-14 border-b border-zinc-800 px-3 shrink-0 gap-2.5",
        isCollapsed && "justify-center"
      )}>
        <div className="w-7 h-7 rounded-lg bg-white flex items-center justify-center shrink-0">
          <FileText size={14} className="text-zinc-900" />
        </div>
        {!isCollapsed && (
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-sm text-white leading-tight truncate">FatihGPT</p>
            <p className="text-xs text-zinc-500 truncate">AI Finance Assistant</p>
          </div>
        )}
        {!isCollapsed && (
          <button
            onClick={() => setIsCollapsed(true)}
            className="p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-all duration-150"
            title="Collapse sidebar"
          >
            <PanelLeftClose size={16} />
          </button>
        )}
      </div>

      {/* Expand button when collapsed */}
      {isCollapsed && (
        <button
          onClick={() => setIsCollapsed(false)}
          className="mt-3 mx-auto p-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-all duration-150"
          title="Expand sidebar"
        >
          <PanelLeftOpen size={16} />
        </button>
      )}

      {/* New Chat Button */}
      <div className="px-3 pt-3 pb-1 shrink-0">
        <button
          onClick={handleNewChat}
          className={cn(
            "w-full flex items-center gap-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition-all duration-150 group",
            isCollapsed ? "justify-center p-2" : "px-3 py-2"
          )}
        >
          <PlusCircle size={16} className="shrink-0 text-zinc-400 group-hover:text-zinc-200 transition-colors" />
          {!isCollapsed && <span className="text-sm font-medium">New Chat</span>}
        </button>
      </div>

      {/* Chat History */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5">
        {loading && !isCollapsed && (
          <p className="text-xs text-zinc-600 px-2 py-1">Loading...</p>
        )}

        {user && chatHistory.length === 0 && !isCollapsed && !loading && (
          <p className="text-xs text-zinc-600 px-2 py-1">No chats yet</p>
        )}

        {/* Pinned section */}
        {!isCollapsed && pinnedChats.length > 0 && (
          <p className="text-[11px] font-semibold text-zinc-600 uppercase tracking-wider px-2 pb-1 pt-2">
            <Pin size={10} className="inline mr-1 -mt-0.5" />
            Pinned
          </p>
        )}
        {pinnedChats.map(chat => renderChatItem(chat))}

        {/* Recent section */}
        {!isCollapsed && recentChats.length > 0 && (
          <p className="text-[11px] font-semibold text-zinc-600 uppercase tracking-wider px-2 pb-1 pt-2">Recent</p>
        )}
        {recentChats.map(chat => renderChatItem(chat))}
      </div>

      {/* Footer */}
      <div className="shrink-0 border-t border-zinc-800 p-3 space-y-0.5">
        {user ? (
          <>
            <div className={cn(
              "flex items-center gap-2.5 px-2 py-1.5 rounded-lg",
              isCollapsed && "justify-center"
            )}>
              <div className="w-6 h-6 rounded-full bg-zinc-700 flex items-center justify-center shrink-0">
                <User size={12} className="text-zinc-300" />
              </div>
              {!isCollapsed && (
                <span className="text-xs text-zinc-500 truncate flex-1">{user.email}</span>
              )}
            </div>
            <button
              onClick={handleLogout}
              className={cn(
                "w-full flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-red-500/10 transition-all duration-150 group",
                isCollapsed && "justify-center"
              )}
            >
              <LogOut size={14} className="text-zinc-600 group-hover:text-red-400 transition-colors shrink-0" />
              {!isCollapsed && (
                <span className="text-sm text-zinc-500 group-hover:text-red-400 transition-colors">Sign out</span>
              )}
            </button>
          </>
        ) : (
          <Link
            href="/login"
            className={cn(
              "flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-zinc-800 transition-all duration-150 group",
              isCollapsed && "justify-center"
            )}
          >
            <User size={14} className="text-zinc-600 group-hover:text-zinc-300 transition-colors shrink-0" />
            {!isCollapsed && (
              <span className="text-sm text-zinc-500 group-hover:text-zinc-200 transition-colors">Sign in</span>
            )}
          </Link>
        )}
      </div>
    </aside>
  )

  function renderChatItem(chat: ChatItem) {
    const isActive = activeChatId === chat.id
    const isMenuOpen = menuOpenId === chat.id

    return (
      <div key={chat.id} className="relative group">
        <button
          onClick={() => handleSelectChat(chat.id)}
          className={cn(
            "w-full flex items-center gap-2.5 px-2 py-1.5 rounded-lg transition-all duration-150 text-left",
            isCollapsed && "justify-center",
            isActive
              ? "bg-zinc-800 text-zinc-100"
              : "hover:bg-zinc-800/60 text-zinc-400 hover:text-zinc-200"
          )}
        >
          <MessageSquare size={14} className="shrink-0 transition-colors" />
          {!isCollapsed && (
            <span className="text-sm truncate flex-1">{chat.title}</span>
          )}
          {!isCollapsed && chat.isPinned && (
            <Pin size={11} className="text-zinc-600 shrink-0" />
          )}
        </button>

        {/* Three-dot menu trigger */}
        {!isCollapsed && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              setMenuOpenId(isMenuOpen ? null : chat.id)
            }}
            className={cn(
              "absolute right-1 top-1/2 -translate-y-1/2 p-1 rounded-md transition-all duration-150",
              isMenuOpen
                ? "opacity-100 bg-zinc-700 text-zinc-200"
                : "opacity-0 group-hover:opacity-100 text-zinc-600 hover:text-zinc-300 hover:bg-zinc-700"
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
                  <span>Unpin Chat</span>
                </>
              ) : (
                <>
                  <Pin size={13} />
                  <span>Pin Chat</span>
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
              <span>Delete Chat</span>
            </button>
          </div>
        )}
      </div>
    )
  }
}
