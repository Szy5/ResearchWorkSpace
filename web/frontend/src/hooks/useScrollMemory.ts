import { RefObject, useLayoutEffect } from 'react'
import { readStored, writeStored } from '../utils/storage'
export default function useScrollMemory(
  ref: RefObject<HTMLElement>,
  key: string,
  ready = true
) {
  useLayoutEffect(() => {
    const element = ref.current
    if (!element || !ready) return
    const stored = readStored<number>(key, 0, true)
    let position =
      typeof stored === 'number' && Number.isFinite(stored) ? stored : 0
    element.scrollTop = position
    const save = () => {
      position = element.scrollTop
      writeStored(key, position, true)
    }
    element.addEventListener('scroll', save, { passive: true })
    return () => {
      element.removeEventListener('scroll', save)
      writeStored(key, position, true)
    }
  }, [ref, key, ready])
}
