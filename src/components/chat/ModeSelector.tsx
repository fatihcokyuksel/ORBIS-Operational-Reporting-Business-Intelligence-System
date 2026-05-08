"use client"

import React from 'react'
import { cn } from '@/lib/utils'
import { BarChart3, ShieldAlert, Scale, Search, FileText, Landmark } from 'lucide-react'

export type ActionMode = string

interface ModeSelectorProps {
  currentMode: ActionMode
  onModeChange: (mode: ActionMode) => void
}

const modes = [
  { id: 'kdv', label: 'KDV Analizi', icon: BarChart3 },
  { id: 'gazete', label: 'Resmi Gazete Taraması', icon: Search },
  { id: 'fatura', label: 'Fatura Risk Kontrolü', icon: ShieldAlert },
  { id: 'mevzuat', label: 'Mevzuat Karşılaştırma', icon: Scale },
  { id: 'bilanco', label: 'Yıllık Bilanço Özeti', icon: Landmark },
  { id: 'cari', label: 'Cari Hesap Denetimi', icon: FileText },
] as const

export function ModeSelector({ currentMode, onModeChange }: ModeSelectorProps) {
  return (
    <div className="flex overflow-x-auto gap-2 mb-4 pb-2 scrollbar-hide whitespace-nowrap" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
      <style dangerouslySetInnerHTML={{__html: `
        .scrollbar-hide::-webkit-scrollbar {
            display: none;
        }
      `}} />
      {modes.map((mode) => {
        const Icon = mode.icon
        const isActive = currentMode === mode.id
        return (
          <button
            key={mode.id}
            onClick={() => onModeChange(mode.id)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 border shrink-0",
              isActive 
                ? "bg-zinc-100 border-zinc-100 text-zinc-950 shadow-sm" 
                : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:bg-zinc-800 hover:border-zinc-700 hover:text-zinc-300"
            )}
          >
            <Icon size={16} className={isActive ? "text-zinc-900" : "text-zinc-500"} />
            {mode.label}
          </button>
        )
      })}
    </div>
  )
}
