import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ChatInterface } from './ChatInterface'
import * as api from '../services/api'
import type { ChatResponse } from '../types'

describe('ChatInterface Component (T028)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('muestra estado vacío con las 4 preguntas de ejemplo clicables', () => {
    render(<ChatInterface />)

    expect(
      screen.getByText('¿Qué le falta a ORG-07 para pasar a producción?'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('¿Cuál es el umbral de aprobación de PLA-ADM?'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('¿Qué tareas tiene pendientes ORG-05?'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('¿Cuáles son las tarifas de almacenamiento en la nube de MIRA?'),
    ).toBeInTheDocument()
  })

  it('al hacer clic en una pregunta de ejemplo llama a sendChat y muestra la respuesta y EvidenceBadge', async () => {
    const mockResponse: ChatResponse = {
      answer: 'Checklist para ORG-05: 10 tareas efectivas registradas.',
      citations: [],
      mcp_traces: [],
      evidence_status: 'COMPLETA',
      action_proposal: null,
    }

    const sendChatSpy = vi.spyOn(api, 'sendChat').mockResolvedValue(mockResponse)
    const onResponseMock = vi.fn()
    const user = userEvent.setup()

    render(<ChatInterface onResponse={onResponseMock} />)

    const exampleBtn = screen.getByText('¿Qué tareas tiene pendientes ORG-05?')
    await user.click(exampleBtn)

    expect(sendChatSpy).toHaveBeenCalledWith({
      message: '¿Qué tareas tiene pendientes ORG-05?',
      organization_context: undefined,
      conversation_history: [],
    })

    await waitFor(() => {
      expect(
        screen.getByText(/Checklist para ORG-05: 10 tareas efectivas registradas/i),
      ).toBeInTheDocument()
      expect(screen.getByText('Respuesta con evidencia')).toBeInTheDocument()
      expect(onResponseMock).toHaveBeenCalledWith(mockResponse)
    })
  })

  it('permite escribir en el textarea y enviar con el botón Enviar', async () => {
    const mockResponse: ChatResponse = {
      answer: 'Respuesta de prueba del asistente',
      citations: [],
      mcp_traces: [],
      evidence_status: 'PARCIAL',
      action_proposal: null,
    }

    vi.spyOn(api, 'sendChat').mockResolvedValue(mockResponse)
    const user = userEvent.setup()

    render(<ChatInterface />)

    const textarea = screen.getByPlaceholderText(/Pregunta sobre criterios de salida/i)
    await user.type(textarea, 'Consulta manual')

    const sendBtn = screen.getByRole('button', { name: /Enviar/i })
    expect(sendBtn).not.toBeDisabled()
    await user.click(sendBtn)

    await waitFor(() => {
      expect(screen.getByText('Consulta manual')).toBeInTheDocument()
      expect(screen.getByText('Respuesta de prueba del asistente')).toBeInTheDocument()
      expect(screen.getByText('Evidencia parcial')).toBeInTheDocument()
    })
  })

  it('muestra mensaje de carga "El asistente está respondiendo…" durante la llamada', async () => {
    let resolvePromise: (value: ChatResponse) => void
    const pendingPromise = new Promise<ChatResponse>((resolve) => {
      resolvePromise = resolve
    })

    vi.spyOn(api, 'sendChat').mockReturnValue(pendingPromise)
    const user = userEvent.setup()

    render(<ChatInterface />)

    const textarea = screen.getByPlaceholderText(/Pregunta sobre criterios de salida/i)
    await user.type(textarea, 'Consulta lenta')

    const sendBtn = screen.getByRole('button', { name: /Enviar/i })
    await user.click(sendBtn)

    expect(screen.getByText(/El asistente está respondiendo…/i)).toBeInTheDocument()
    expect(sendBtn).toBeDisabled()

    // Resolver promesa
    resolvePromise!({
      answer: 'Respuesta completada',
      citations: [],
      mcp_traces: [],
      evidence_status: 'COMPLETA',
      action_proposal: null,
    })

    await waitFor(() => {
      expect(screen.queryByText(/El asistente está respondiendo…/i)).not.toBeInTheDocument()
      expect(screen.getByText('Respuesta completada')).toBeInTheDocument()
    })
  })

  it('si sendChat lanza ApiClientError muestra tarjeta de error sin crear mensaje del asistente', async () => {
    vi.spyOn(api, 'sendChat').mockRejectedValue(
      new api.ApiClientError(
        'FORBIDDEN_ORGANIZATION_ACCESS',
        'El usuario U-I1 no tiene permisos de acceso sobre la organización ORG-06.',
        'PR-7',
        403,
      ),
    )
    const user = userEvent.setup()

    render(<ChatInterface />)

    const textarea = screen.getByPlaceholderText(/Pregunta sobre criterios de salida/i)
    await user.type(textarea, 'Consulta ORG-06')

    const sendBtn = screen.getByRole('button', { name: /Enviar/i })
    await user.click(sendBtn)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
      expect(
        screen.getByText(/El usuario U-I1 no tiene permisos de acceso sobre la organización ORG-06/i),
      ).toBeInTheDocument()
      expect(screen.getByText(/Principio: PR-7/i)).toBeInTheDocument()
    })

    // No debe haber burbujas de respuesta del asistente
    expect(screen.queryByText(/Respuesta con evidencia/i)).not.toBeInTheDocument()
  })

  it('notifica onActionProposal cuando la respuesta contiene action_proposal', async () => {
    const mockProposal = {
      action_type: 'CAMBIO_ESTADO_TAREA',
      tarea_id: 'T-006',
      org_id: 'ORG-05',
      estado_actual: 'en_curso' as const,
      estado_propuesto: 'completada' as const,
      justificacion: 'Se habilitó carpeta SFTP',
      confirmation_token: 'token-t006',
      expires_at: '2026-11-07T16:00:00Z',
    }

    vi.spyOn(api, 'sendChat').mockResolvedValue({
      answer: 'Propuesta lista',
      citations: [],
      mcp_traces: [],
      evidence_status: 'COMPLETA',
      action_proposal: mockProposal,
    })

    const onActionProposalMock = vi.fn()
    const user = userEvent.setup()

    render(<ChatInterface onActionProposal={onActionProposalMock} />)

    const textarea = screen.getByPlaceholderText(/Pregunta sobre criterios de salida/i)
    await user.type(textarea, 'Marcar T-006')

    await user.click(screen.getByRole('button', { name: /Enviar/i }))

    await waitFor(() => {
      expect(onActionProposalMock).toHaveBeenCalledWith(mockProposal)
      expect(
        screen.getByText(/Propuesta de acción preparada para la tarea T-006/i),
      ).toBeInTheDocument()
    })
  })

  it('renderiza CitationCard debajo de EvidenceBadge con la primera cita abierta por defecto', async () => {
    vi.spyOn(api, 'sendChat').mockResolvedValue({
      answer: 'Según la normativa, el umbral es 80%.',
      evidence_status: 'COMPLETA',
      mcp_traces: [],
      citations: [
        {
          chunk_id: 'GUI-INC_v2#sec3',
          doc_code: 'GUI-INC_v2',
          doc_title: 'Guía de Incorporación',
          section: '§3',
          version: 'v2',
          status: 'vigente',
          excerpt: 'El umbral de aprobación técnica es del 80%.',
        },
        {
          chunk_id: 'POL-SEG_v1#sec2',
          doc_code: 'POL-SEG_v1',
          doc_title: 'Política de Seguridad',
          section: '§2',
          version: 'v1',
          status: 'derogada',
          excerpt: 'Umbral anterior 70%.',
        },
      ],
      action_proposal: null,
    })

    const user = userEvent.setup()
    render(<ChatInterface />)

    const textarea = screen.getByPlaceholderText(/Pregunta sobre criterios de salida/i)
    await user.type(textarea, 'Consulta sobre umbral')
    await user.click(screen.getByRole('button', { name: /Enviar/i }))

    await waitFor(() => {
      expect(screen.getByText('Citas documentales (2):')).toBeInTheDocument()
      expect(screen.getByText('GUI-INC_v2')).toBeInTheDocument()
      expect(screen.getByText('POL-SEG_v1')).toBeInTheDocument()

      // La primera cita aparece abierta por defecto
      expect(
        screen.getByText('El umbral de aprobación técnica es del 80%.'),
      ).toBeInTheDocument()

      // La segunda cita aparece cerrada por defecto
      expect(screen.queryByText('Umbral anterior 70%.')).not.toBeInTheDocument()
    })
  })
})

