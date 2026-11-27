/** Browser storage is optional (private mode, quota and older snapshots). */
export function readStored<T>(key: string, fallback: T, session = false): T {
  try {
    return (
      JSON.parse(
        (session ? sessionStorage : localStorage).getItem(key) ?? 'null'
      ) ?? fallback
    )
  } catch {
    return fallback
  }
}
export function writeStored(key: string, value: unknown, session = false) {
  try {
    ;(session ? sessionStorage : localStorage).setItem(
      key,
      JSON.stringify(value)
    )
  } catch {
    /* The UI remains usable without storage. */
  }
}
