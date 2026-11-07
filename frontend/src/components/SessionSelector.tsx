import { useEffect, useState } from 'react'
import type { SimulatedUser } from '../types'
import { listUsers, switchSession, setSessionToken } from '../services/api'
import { User, Shield, Building2, AlertCircle, Loader2 } from 'lucide-react'

export interface SessionSelectorProps {
  onSessionChange?: (user: SimulatedUser) => void
  className?: string
}

const ROLE_LABELS: Record<string, string> = {
  ejecutivo_implementacion: 'Ejecutivo de implementación',
  jefe_implementacion: 'Jefe de implementación',
  comercial: 'Comercial',
}

export function SessionSelector({ onSessionChange, className = '' }: SessionSelectorProps) {
  const [users, setUsers] = useState<SimulatedUser[]>([])
  const [activeUser, setActiveUser] = useState<SimulatedUser | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [switching, setSwitching] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    async function initUsers() {
      try {
        setLoading(true)
        setError(null)
        const userList = await listUsers()
        if (!isMounted) return

        setUsers(userList)

        // Por defecto selecciona U-I1
        const defaultUser = userList.find((u) => u.usuario_id === 'U-I1') || userList[0]
        if (defaultUser) {
          const sessionRes = await switchSession(defaultUser.usuario_id)
          if (!isMounted) return
          setSessionToken(sessionRes.session_token)
          setActiveUser(sessionRes.user)
          onSessionChange?.(sessionRes.user)
        }
      } catch (err) {
        if (!isMounted) return
        setError(
          err instanceof Error
            ? err.message
            : 'Error al inicializar las identidades de demostración.',
        )
      } finally {
        if (isMounted) setLoading(false)
      }
    }

    void initUsers()

    return () => {
      isMounted = false
    }
  }, [onSessionChange])

  const handleUserChange = async (userId: string) => {
    try {
      setSwitching(true)
      setError(null)
      const sessionRes = await switchSession(userId)
      setSessionToken(sessionRes.session_token)
      setActiveUser(sessionRes.user)
      onSessionChange?.(sessionRes.user)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Error al cambiar la sesión simulada. Intenta nuevamente.',
      )
    } finally {
      setSwitching(false)
    }
  }

  return (
    <header
      role="region"
      aria-label="Selector de identidad de usuario"
      className={`w-full border-b border-slate-200 bg-white px-4 py-3 shadow-sm ${className}`}
    >
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
        {/* Selector accesible */}
        <div className="flex items-center gap-3">
          <label
            htmlFor="session-user-select"
            className="text-xs font-semibold uppercase tracking-wider text-slate-600"
          >
            Usuario simulado:
          </label>
          <div className="relative">
            <select
              id="session-user-select"
              aria-label="Seleccionar usuario simulado"
              disabled={loading || switching}
              value={activeUser?.usuario_id || ''}
              onChange={(e) => void handleUserChange(e.target.value)}
              className="rounded-md border border-slate-300 bg-white py-1.5 pl-3 pr-8 text-sm font-medium text-slate-800 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
            >
              {loading && <option value="">Cargando usuarios...</option>}
              {users.map((user) => (
                <option key={user.usuario_id} value={user.usuario_id}>
                  {user.usuario_id} - {user.nombre} ({ROLE_LABELS[user.rol] || user.rol})
                </option>
              ))}
            </select>
            {(loading || switching) && (
              <span className="absolute right-2 top-2.5">
                <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
              </span>
            )}
          </div>
        </div>

        {/* Ficha del usuario activo */}
        {activeUser && (
          <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600">
            <div className="flex items-center gap-1.5">
              <User className="h-3.5 w-3.5 text-slate-400" />
              <span className="font-semibold text-slate-800">{activeUser.nombre}</span>
              <span className="text-slate-400">({activeUser.usuario_id})</span>
            </div>

            <div className="flex items-center gap-1.5">
              <Shield className="h-3.5 w-3.5 text-slate-400" />
              <span className="rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
                {ROLE_LABELS[activeUser.rol] || activeUser.rol}
              </span>
            </div>

            <div className="flex items-center gap-1.5">
              <Building2 className="h-3.5 w-3.5 text-slate-400" />
              <span>Organizaciones:</span>
              <span className="font-medium text-slate-800">
                {activeUser.orgs_asignadas.length > 0
                  ? activeUser.orgs_asignadas.join(', ')
                  : 'Ninguna'}
              </span>
            </div>
          </div>
        )}

        {/* Aviso visible y discreto */}
        <div className="w-full text-right sm:w-auto">
          <p className="text-[11px] text-slate-500">
            Sesión simulada solo para demostración académica; no es autenticación real.
          </p>
        </div>
      </div>

      {/* Manejo de errores */}
      {error && (
        <div
          role="alert"
          className="mt-2 flex items-center gap-2 rounded bg-rose-50 px-3 py-1.5 text-xs text-rose-700 border border-rose-200"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </header>
  )
}