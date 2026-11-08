import { useState, useRef, useEffect } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  X,
  Loader2,
  ShieldAlert,
  ArrowRight,
  Clock,
} from 'lucide-react'
import type { ActionProposal, ActionConfirmResponse, SimulatedUser } from '../types'
import { prepareAction, confirmAction, ApiClientError, getSessionToken } from '../services/api'

export interface ActionConfirmationModalProps {
  isOpen: boolean
  proposal: ActionProposal | null
  onClose: () => void
  onSuccess?: (response: ActionConfirmResponse) => void
  currentUser?: SimulatedUser | null
  sessionEpoch?: number
}

interface ErrorDetails {
  message: string
  principleViolated?: string | null
}

export function ActionConfirmationModal({
  isOpen,
  proposal,
  onClose,
  onSuccess,
  currentUser,
  sessionEpoch = 0,
}: ActionConfirmationModalProps) {
  // Token efímero de confirmación retenido estrictamente en memoria (nunca renderizado ni logueado)
  const [internalToken, setInternalToken] = useState<string | null>(null)
  const [isPreparing, setIsPreparing] = useState(false)
  const [isConfirming, setIsConfirming] = useState(false)
  const [preparedSummary, setPreparedSummary] = useState<string | null>(null)
  const [successResult, setSuccessResult] = useState<ActionConfirmResponse | null>(null)
  const [error, setError] = useState<ErrorDetails | null>(null)
  const [prevProposalKey, setPrevProposalKey] = useState<string | null>(null)

  const activeUserId = currentUser?.usuario_id || getSessionToken() || 'anonymous'
  // currentProposalKey incluye tarea_id, org_id, nuevo_estado, justificacion y el usuario de la sesión
  const currentProposalKey =
    isOpen && proposal
      ? `${proposal.tarea_id}-${proposal.org_id}-${proposal.estado_propuesto}-${proposal.justificacion}-${activeUserId}`
      : null

  const sessionEpochRef = useRef(sessionEpoch)
  const abortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (sessionEpochRef.current !== sessionEpoch) {
      abortControllerRef.current?.abort()
      abortControllerRef.current = null
      sessionEpochRef.current = sessionEpoch
      setInternalToken(null)
      setPreparedSummary(null)
      setSuccessResult(null)
      setError(null)
      setIsPreparing(false)
      setIsConfirming(false)
    }
  }, [sessionEpoch])

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort()
      abortControllerRef.current = null
    }
  }, [])

  // Ajustar estado durante render si cambia la propuesta o el usuario de la sesión
  if (currentProposalKey !== prevProposalKey) {
    setPrevProposalKey(currentProposalKey)
    setInternalToken(null)
    setPreparedSummary(null)
    setSuccessResult(null)
    setError(null)
    setIsPreparing(false)
    setIsConfirming(false)
  }

  if (!isOpen || !proposal) {
    return null
  }

  const handleClose = () => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setInternalToken(null)
    setPreparedSummary(null)
    setSuccessResult(null)
    setError(null)
    setIsPreparing(false)
    setIsConfirming(false)
    onClose()
  }

  const handlePrepare = async () => {
    setError(null)
    setIsPreparing(true)

    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller
    const requestEpoch = sessionEpochRef.current

    try {
      // Llamada formal a prepareAction({ action_type, target_id, payload, org_id })
      const res = await prepareAction(
        {
          action_type: proposal.action_type,
          target_id: proposal.tarea_id,
          payload: {
            nuevo_estado: proposal.estado_propuesto,
            justificacion: proposal.justificacion,
            org_id: proposal.org_id,
          },
          tarea_id: proposal.tarea_id,
          org_id: proposal.org_id,
          nuevo_estado: proposal.estado_propuesto,
          justificacion: proposal.justificacion,
        },
        controller.signal,
      )

      // Ignorar si la época cambió, el modal se cerró o la petición se abortó
      if (
        requestEpoch !== sessionEpochRef.current ||
        controller.signal.aborted ||
        abortControllerRef.current !== controller
      ) {
        return
      }

      // Validar coincidencia de la respuesta de prepareAction con la propuesta mostrada
      const prep = res.proposal
      const matches =
        prep.tarea_id === proposal.tarea_id &&
        prep.org_id === proposal.org_id &&
        prep.estado_propuesto === proposal.estado_propuesto &&
        prep.justificacion === proposal.justificacion

      if (!matches) {
        setInternalToken(null)
        setPreparedSummary(null)
        setError({
          message:
            'Los datos de la propuesta preparada por el servidor no coinciden con la acción solicitada. Confirmación deshabilitada por seguridad (PR-1, PR-6).',
          principleViolated: 'PR-6',
        })
        return
      }

      // Guardar token efímero internamente sin imprimirlo en consola ni en el DOM
      setInternalToken(res.proposal.confirmation_token)
      setPreparedSummary(
        `Acción preparada para la tarea ${res.proposal.tarea_id} (${res.proposal.org_id}). Nuevo estado: ${res.proposal.estado_propuesto}. Token de confirmación efímero emitido con vigencia de 5 minutos.`,
      )
    } catch (err) {
      if (
        requestEpoch !== sessionEpochRef.current ||
        controller.signal.aborted ||
        abortControllerRef.current !== controller
      ) {
        return
      }

      if (err instanceof ApiClientError) {
        setError({
          message: err.message,
          principleViolated: err.principleViolated || null,
        })
      } else {
        setError({
          message:
            err instanceof Error
              ? err.message
              : 'Ocurrió un error inesperado al preparar la acción.',
        })
      }
    } finally {
      if (
        requestEpoch === sessionEpochRef.current &&
        !controller.signal.aborted &&
        abortControllerRef.current === controller
      ) {
        setIsPreparing(false)
      }
    }
  }

  const handleConfirm = async () => {
    if (!internalToken) {
      setError({
        message: 'No existe un token de confirmación preparado para ejecutar esta acción.',
        principleViolated: 'PR-6',
      })
      return
    }

    setError(null)
    setIsConfirming(true)

    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller
    const requestEpoch = sessionEpochRef.current

    try {
      // confirmAction envía el token efímero sin imprimirlo
      const res = await confirmAction(internalToken, controller.signal)

      // Ignorar si la época cambió, el modal se cerró o la petición se abortó
      if (
        requestEpoch !== sessionEpochRef.current ||
        controller.signal.aborted ||
        abortControllerRef.current !== controller
      ) {
        return
      }

      setSuccessResult(res)
      onSuccess?.(res)
    } catch (err) {
      if (
        requestEpoch !== sessionEpochRef.current ||
        controller.signal.aborted ||
        abortControllerRef.current !== controller
      ) {
        return
      }

      if (err instanceof ApiClientError) {
        setError({
          message: err.message,
          principleViolated: err.principleViolated || null,
        })
      } else {
        setError({
          message:
            err instanceof Error
              ? err.message
              : 'Ocurrió un error inesperado al confirmar la acción.',
        })
      }
    } finally {
      if (
        requestEpoch === sessionEpochRef.current &&
        !controller.signal.aborted &&
        abortControllerRef.current === controller
      ) {
        setIsConfirming(false)
      }
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-action-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in"
    >
      <div className="relative w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-2xl space-y-5 text-slate-900">
        {/* Cabecera del modal */}
        <div className="flex items-start justify-between border-b border-slate-200 pb-3">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-indigo-50 p-2 text-indigo-700">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <div>
              <h2
                id="modal-action-title"
                className="text-base font-bold text-slate-900"
              >
                Confirmación de acción requerida
              </h2>
              <span className="text-xs text-slate-500">
                Protocolo de Evidencia y Control (PR-1, PR-6)
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Cerrar modal de confirmación"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Mensaje de éxito al completar */}
        {successResult ? (
          <div className="space-y-4 py-2">
            <div
              role="status"
              className="flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-emerald-900"
            >
              <CheckCircle2 className="h-6 w-6 shrink-0 text-emerald-600 mt-0.5" />
              <div className="space-y-1 text-sm">
                <p className="font-bold">¡Acción ejecutada y confirmada con éxito!</p>
                <p className="text-xs text-emerald-800">
                  La tarea {successResult.tarea_id} ({successResult.org_id}) ha cambiado a estado{' '}
                  <span className="font-semibold">{successResult.nuevo_estado}</span>.
                </p>
                <p className="text-[11px] text-emerald-700">
                  Evento de auditoría registrado con identificador #{successResult.evento_id}.
                </p>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={handleClose}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                Entendido y cerrar
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Aviso normativo PR-1 y PR-6 */}
            <aside
              role="note"
              className="rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-xs text-amber-900 flex items-start gap-2.5"
            >
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
              <div>
                <p className="font-semibold">Decisión humana obligatoria</p>
                <p className="text-amber-800">
                  El asistente no ejecuta mutaciones autónomas. Toda modificación de estado
                  requiere preparación y confirmación explícita por una persona responsable.
                </p>
              </div>
            </aside>

            {/* Detalle de la propuesta de acción */}
            <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3.5 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="font-semibold text-slate-500 uppercase tracking-wider text-[10px]">
                    Identificador de tarea
                  </span>
                  <p className="font-mono font-bold text-slate-800 text-sm">
                    {proposal.tarea_id}
                  </p>
                </div>
                <div>
                  <span className="font-semibold text-slate-500 uppercase tracking-wider text-[10px]">
                    Organización
                  </span>
                  <p className="font-mono font-bold text-slate-800 text-sm">
                    {proposal.org_id}
                  </p>
                </div>
              </div>

              <div>
                <span className="font-semibold text-slate-500 uppercase tracking-wider text-[10px]">
                  Transición de estado
                </span>
                <div className="mt-1 flex items-center gap-2">
                  <span className="inline-flex items-center rounded-md border border-slate-300 bg-white px-2 py-1 font-mono font-medium text-slate-700">
                    {proposal.estado_actual}
                  </span>
                  <ArrowRight className="h-4 w-4 text-slate-400" />
                  <span className="inline-flex items-center rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 font-mono font-bold text-indigo-700">
                    {proposal.estado_propuesto}
                  </span>
                </div>
              </div>

              <div>
                <span className="font-semibold text-slate-500 uppercase tracking-wider text-[10px]">
                  Justificación de la propuesta
                </span>
                <p className="mt-0.5 whitespace-pre-wrap text-slate-700">
                  {proposal.justificacion}
                </p>
              </div>

              <div className="border-t border-slate-200 pt-2 text-[11px] text-slate-600">
                <span className="font-semibold text-slate-700">Impacto estimado: </span>
                <span>
                  Se registrará un evento de mutación inmutable en SQLite (tabla tarea_eventos_cambio)
                  preservando los registros base y recalculando el porcentaje de avance de la
                  organización.
                </span>
              </div>
            </div>

            {/* Tarjeta de resumen tras preparar */}
            {preparedSummary && (
              <div
                role="status"
                className="flex items-start gap-2.5 rounded-lg border border-sky-200 bg-sky-50 p-3 text-xs text-sky-900"
              >
                <Clock className="h-4 w-4 shrink-0 text-sky-600 mt-0.5" />
                <div className="space-y-0.5">
                  <p className="font-bold">Paso 1 completado: Acción preparada</p>
                  <p className="text-sky-800">{preparedSummary}</p>
                </div>
              </div>
            )}

            {/* Alerta de error si la llamada falla */}
            {error && (
              <div
                role="alert"
                className="flex items-start gap-2.5 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-900"
              >
                <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-bold">Error en la operación</p>
                  <p className="text-rose-800">{error.message}</p>
                  {error.principleViolated && (
                    <span className="inline-block rounded border border-rose-300 bg-rose-100 px-1.5 py-0.5 font-mono text-[10px] font-bold text-rose-800">
                      Principio violado: {error.principleViolated}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Botones de acción */}
            <div className="flex items-center justify-end gap-3 border-t border-slate-200 pt-4">
              <button
                type="button"
                onClick={handleClose}
                disabled={isPreparing || isConfirming}
                className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
              >
                Cancelar
              </button>

              {!internalToken ? (
                <button
                  type="button"
                  onClick={() => void handlePrepare()}
                  disabled={isPreparing}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
                >
                  {isPreparing ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Preparando acción...</span>
                    </>
                  ) : (
                    <span>Preparar acción</span>
                  )}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => void handleConfirm()}
                  disabled={isConfirming}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
                >
                  {isConfirming ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Confirmando y ejecutando...</span>
                    </>
                  ) : (
                    <span>Confirmar y ejecutar</span>
                  )}
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default ActionConfirmationModal
