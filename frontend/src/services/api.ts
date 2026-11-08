/**
 * Cliente HTTP y servicios API para el frontend de MIRA CU-3
 * Integración con FastAPI y delegación en mocks de desarrollo
 */

import type {
  SimulatedUser,
  SessionTokenResponse,
  ChatRequest,
  ChatResponse,
  ActionPrepareRequest,
  ActionPrepareResponse,
  ActionConfirmRequest,
  ActionConfirmResponse,
  ApiError,
} from '../types'
import {
  mockListUsers,
  mockSwitchSession,
  mockSendChat,
  mockPrepareAction,
  mockConfirmAction,
} from './mocks'

export class ApiClientError extends Error {
  code: string
  override message: string
  principleViolated?: string | null
  status?: number

  constructor(
    code: string,
    message: string,
    principleViolated?: string | null,
    status?: number,
  ) {
    super(message)
    this.name = 'ApiClientError'
    this.code = code
    this.message = message
    this.principleViolated = principleViolated
    this.status = status
  }
}

let currentSessionToken: string | null = null

export function setSessionToken(token: string | null): void {
  currentSessionToken = token
}

export function getSessionToken(): string | null {
  return currentSessionToken
}

export function isMockMode(): boolean {
  return import.meta.env.VITE_USE_MOCKS === 'true'
}

const REQUEST_TIMEOUT_MS = 60000

async function requestWithTimeout<T>(
  path: string,
  options: RequestInit = {},
  externalSignal?: AbortSignal,
): Promise<T> {
  const baseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const url = `${baseUrl}${normalizedPath}`

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  const abortListener = () => {
    controller.abort()
  }

  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort()
    } else {
      externalSignal.addEventListener('abort', abortListener)
    }
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  }

  if (currentSessionToken) {
    headers['Authorization'] = `Bearer ${currentSessionToken}`
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    })

    if (!response.ok) {
      let apiError: ApiError | null = null
      try {
        apiError = (await response.json()) as ApiError
      } catch {
        // La respuesta no era JSON
      }

      throw new ApiClientError(
        apiError?.code || 'HTTP_ERROR',
        apiError?.message || `Error en la llamada al servidor (${response.status})`,
        apiError?.principle_violated || null,
        response.status,
      )
    }

    return (await response.json()) as T
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error
    }
    throw new ApiClientError(
      'SERVICE_UNAVAILABLE',
      'El servicio no está disponible en este momento. Intenta nuevamente en unos minutos.',
      null,
      0,
    )
  } finally {
    clearTimeout(timeoutId)
    if (externalSignal) {
      externalSignal.removeEventListener('abort', abortListener)
    }
  }
}

export async function listUsers(): Promise<SimulatedUser[]> {
  if (isMockMode()) {
    return mockListUsers()
  }
  return requestWithTimeout<SimulatedUser[]>('/api/session/users')
}

export async function switchSession(userId: string): Promise<SessionTokenResponse> {
  if (isMockMode()) {
    const res = await mockSwitchSession(userId)
    setSessionToken(res.session_token)
    return res
  }
  const res = await requestWithTimeout<SessionTokenResponse>('/api/session/switch', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId }),
  })
  setSessionToken(res.session_token)
  return res
}

export async function sendChat(
  request: ChatRequest,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  if (isMockMode()) {
    return mockSendChat(request)
  }
  return requestWithTimeout<ChatResponse>(
    '/api/chat',
    {
      method: 'POST',
      body: JSON.stringify(request),
    },
    signal,
  )
}

export async function prepareAction(
  request: ActionPrepareRequest,
): Promise<ActionPrepareResponse> {
  if (isMockMode()) {
    return mockPrepareAction(request)
  }
  return requestWithTimeout<ActionPrepareResponse>('/api/action/prepare', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function confirmAction(
  confirmationToken: string,
): Promise<ActionConfirmResponse> {
  if (isMockMode()) {
    return mockConfirmAction(confirmationToken)
  }
  const body: ActionConfirmRequest = { confirmation_token: confirmationToken }
  return requestWithTimeout<ActionConfirmResponse>('/api/action/confirm', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}