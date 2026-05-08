"use client"

import React, { useState } from 'react'
import { MessageSquare, PlusCircle, Settings, User, ChevronLeft, ChevronRight, FileText } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Sidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false)

  const chatHistory = [
    { id: 1, title: 'Q1 KDV Analizi', date: 'Bugün' },
    { id: 2, title: 'Yıllık Bilanço Özeti', date: 'Dün' },
    { id: 3, title: 'Resmi Gazete Taraması', date: '15 Mart' },
  ]

  return (
    <aside 
      className={cn(
        "flex flex-col h-screen bg-zinc-900 text-zinc-300 transition-all duration-300 relative border-r border-zinc-800",
        isCollapsed ? "w-20" : "w-72"
      )}
    >
      {/* Toggle Button */}
      <button 
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="absolute -right-3 top-6 bg-zinc-800 border border-zinc-700 text-zinc-300 rounded-full p-1 hover:bg-zinc-700 transition-colors z-10"
      >
        {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>

      {/* Header */}
      <div className="p-4 flex items-center gap-3 border-b border-zinc-800">
        <div className="w-10 h-10 rounded-lg bg-zinc-100/20 text-zinc-100 flex items-center justify-center shrink-0">
          <FileText size={24} />
        </div>
        {!isCollapsed && (
          <div className="flex flex-col">
            <span className="font-semibold text-white tracking-wide">FinAI Assistant</span>
            <span className="text-xs text-zinc-500">Accounting & Finance</span>
          </div>
        )}
      </div>

      {/* New Audit Button */}
      <div className="p-4">
        <button className={cn(
          "w-full flex items-center justify-center gap-2 bg-zinc-100 hover:bg-white text-zinc-950 rounded-lg py-2.5 transition-colors shadow-sm",
          isCollapsed ? "px-0" : "px-4"
        )}>
          <PlusCircle size={20} />
          {!isCollapsed && <span className="font-medium">Yeni Denetim</span>}
        </button>
      </div>

      {/* History */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
        {!isCollapsed && (
          <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3 px-3">Recent Audits</h3>
        )}
        {chatHistory.map((chat) => (
          <button 
            key={chat.id}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-zinc-800 transition-colors group",
              isCollapsed && "justify-center"
            )}
          >
            <MessageSquare size={18} className="text-zinc-500 group-hover:text-zinc-300" />
            {!isCollapsed && (
              <div className="flex flex-col items-start truncate">
                <span className="text-sm font-medium text-zinc-300 group-hover:text-white truncate">{chat.title}</span>
              </div>
            )}
          </button>
        ))}
      </div>

      {/* Footer Profile/Settings */}
      <div className="p-4 border-t border-zinc-800 space-y-2">
        <button className={cn(
          "w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-zinc-800 transition-colors text-zinc-400 hover:text-white",
          isCollapsed && "justify-center"
        )}>
          <Settings size={20} />
          {!isCollapsed && <span className="text-sm font-medium">Settings</span>}
        </button>
        <button className={cn(
          "w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-zinc-800 transition-colors text-zinc-400 hover:text-white",
          isCollapsed && "justify-center"
        )}>
          <User size={20} />
          {!isCollapsed && <span className="text-sm font-medium">Ahmet Yılmaz</span>}
        </button>
      </div>
    </aside>
  )
}
