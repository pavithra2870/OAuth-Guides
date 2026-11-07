import { createContext, useContext } from 'react'

export const LibraryContext = createContext(null)

export function useLibrary() {
  const ctx = useContext(LibraryContext)
  if (!ctx) throw new Error('useLibrary must be used inside LibraryProvider')
  return ctx
}
