"use client"

import React, { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { modeGroups } from './modeCatalog'

export type ActionMode = string

interface ModeSelectorProps {
  currentMode: ActionMode
  onModeChange: (mode: ActionMode) => void
}

export function ModeSelector({ currentMode, onModeChange }: ModeSelectorProps) {
  const [activeGroupId, setActiveGroupId] = useState<string | null>(null)
  const [hasOverflow, setHasOverflow] = useState(false)
  const [isMenuReady, setIsMenuReady] = useState(false)
  const internalResetRef = useRef(false)
  const prevModeRef = useRef(currentMode)
  const scrollRef = useRef<HTMLDivElement>(null)
  const activeGroup = modeGroups.find((group) => group.id === activeGroupId)

  useEffect(() => {
    const wasModeCleared = prevModeRef.current && !currentMode
    if (wasModeCleared && activeGroupId) {
      const prevGroup = modeGroups.find((group) => group.items.some((item) => item.id === prevModeRef.current))
      if (prevGroup && activeGroupId === prevGroup.id) {
        if (internalResetRef.current) {
          internalResetRef.current = false
        } else {
          setActiveGroupId(null)
        }
      }
    }
    prevModeRef.current = currentMode
  }, [activeGroupId, currentMode])

  useEffect(() => {
    if (!currentMode) return
    const matchingGroup = modeGroups.find((group) => group.items.some((item) => item.id === currentMode))
    if (matchingGroup && matchingGroup.id !== activeGroupId) {
      setActiveGroupId(matchingGroup.id)
    }
  }, [activeGroupId, currentMode])

  useEffect(() => {
    let timeoutId: number | undefined
    let resizeObserver: ResizeObserver | undefined

    const updateOverflow = () => {
      const scrollElement = scrollRef.current
      setHasOverflow(Boolean(scrollElement && scrollElement.scrollWidth > scrollElement.clientWidth + 1))
      setIsMenuReady(true)
    }

    queueMicrotask(() => {
      setHasOverflow(false)
      setIsMenuReady(false)
    })

    if (activeGroupId) {
      timeoutId = window.setTimeout(() => {
        updateOverflow()
        if (scrollRef.current && 'ResizeObserver' in window) {
          resizeObserver = new ResizeObserver(updateOverflow)
          resizeObserver.observe(scrollRef.current)
        }
      }, 340)
    }

    return () => {
      if (timeoutId) window.clearTimeout(timeoutId)
      resizeObserver?.disconnect()
    }
  }, [activeGroupId])

  const handleMainClick = (groupId: string) => {
    setActiveGroupId(groupId)
    onModeChange('')
  }

  const handleReset = () => {
    setActiveGroupId(null)
    onModeChange('')
  }

  const handleSubItemClick = (itemId: string, isActive: boolean) => {
    if (isActive) {
      internalResetRef.current = true
      onModeChange('')
    } else {
      onModeChange(itemId)
    }
  }

  if (!activeGroup) {
    return (
      <div className="mode-strip-enter-main flex w-full sm:justify-center overflow-x-auto gap-2 pb-2 whitespace-nowrap scrollbar-hide px-2 sm:px-0">
        {modeGroups.map((group) => {
          const Icon = group.icon
          return (
            <button
              key={group.id}
              onClick={() => handleMainClick(group.id)}
              className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 border shrink-0 bg-zinc-900 border-zinc-800 text-zinc-300 hover:bg-zinc-800 hover:border-zinc-700 hover:text-zinc-100"
            >
              <Icon size={16} className="text-zinc-500" />
              {group.label}
            </button>
          )
        })}
      </div>
    )
  }

  return (
    <div
      ref={scrollRef}
      className={cn(
        'mode-menu-scroll w-full overflow-x-auto pb-2 whitespace-nowrap',
        isMenuReady && hasOverflow && 'mode-menu-scroll-visible'
      )}
    >
      <div className="mode-strip-active flex w-max gap-2">
        <button
          onClick={handleReset}
          className="group flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold transition-all duration-200 border shrink-0 bg-white border-white text-zinc-950 shadow-sm"
          title="Ana fonksiyonlara don"
        >
          <X size={16} className="text-zinc-900" />
          {activeGroup.label}
        </button>

        {activeGroup.items.map((item) => {
          const Icon = item.icon
          const isActive = currentMode === item.id
          return (
            <button
              key={item.id}
              onClick={() => handleSubItemClick(item.id, isActive)}
              className={cn(
                'group flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 border shrink-0',
                isActive
                  ? 'bg-zinc-100 border-zinc-100 text-zinc-950 shadow-sm'
                  : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:bg-zinc-800 hover:border-zinc-700 hover:text-zinc-200'
              )}
              title={isActive ? 'Secimi kaldir' : undefined}
            >
              {isActive ? <X size={16} className="text-zinc-900" /> : <Icon size={16} className="text-zinc-500" />}
              {item.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
