export function normalizeQuotes(text: string): string {
  return text.replace(/《([^《》]*)》/g, '"$1"')
}
