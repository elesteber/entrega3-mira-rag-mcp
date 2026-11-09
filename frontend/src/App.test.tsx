import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import App from './App'
import * as api from './services/api'
import type { SimulatedUser, SessionTokenResponse, ChatResponse } from './types'

describe('App Component (T023 / T054)', () => {
  const mockUsers: SimulatedUser[] = [
    {
      usuario_id: 'U-I1',
      nombre: 'Elena Morales',
      rol: 'ejecutivo_implementacion',
      orgs_asignadas: ['ORG-05', 'ORG-07'],
    },
    {
      usuario_id: 'U-I2',
      nombre: 'Carlos Ruiz',
      rol: 'ejecutivo_implementacion',
      orgs_asignadas: ['ORG-06'],
    },
  ]

  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'listUsers').mockResolvedValue(mockUsers)
    vi.spyOn(api, 'switchSession').mockImplementation(async (userId: string): Promise<SessionTokenResponse> => {
      const user = mockUsers.find((u) => u.usuario_id === userId) || mockUsers[0]
      return {
        session_token: `mock-token-${user.usuario_id}`,
        user,
        expires_at: '2026-11-07T23:59:59Z',
      }
    })
  })

  it('renderiza el título del asistente', async () => {
    render(<App />)
    expect(screen.getByText('MIRA · Asistente de incorporación')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /seleccionar usuario simulado/i })).toHaveValue('U-I1')
    })
  })

  it('muestra el aviso visible de datos simulados en modo mock', async () => {
    render(<App />)
    expect(screen.getByText('Datos simulados')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /seleccionar usuario simulado/i })).toHaveValue('U-I1')
    })
  })

  it('renderiza el layout de dos columnas con SessionSelector, ChatInterface y el panel reservado Trazas MCP', async () => {
    render(<App />)

    // Selector de sesión accesible
    expect(screen.getByRole('combobox', { name: /seleccionar usuario simulado/i })).toBeInTheDocument()

    // Panel reservado a la derecha
    expect(screen.getByRole('heading', { level: 2, name: 'Trazas MCP' })).toBeInTheDocument()
    expect(screen.getByText('Aún sin consultas')).toBeInTheDocument()

    // ChatInterface a la izquierda con preguntas de ejemplo
    await waitFor(() => {
      expect(screen.getByText('¿Qué le falta a ORG-07 para pasar a producción?')).toBeInTheDocument()
    })
  })

  it('al cambiar la sesión se limpia la conversación del chat y las trazas MCP', async () => {
    const user = userEvent.setup()
    const mockChatResponse: ChatResponse = {
      answer: 'Respuesta de prueba sobre ORG-07',
      citations: [
        {
          chunk_id: 'GUI-INC_v2#sec3_1',
          doc_code: 'GUI-INC_v2',
          doc_title: 'Guía de Incorporación',
          section: '§3.1',
          version: 'v2',
          status: 'vigente',
          excerpt: 'Requisitos de salida a producción.',
        },
      ],
      evidence_status: 'COMPLETA',
      mcp_traces: [
        {
          tool_name: 'consultar_integracion',
          parameters: { org_id: 'ORG-07' },
          response_summary: 'Telemetría OK',
          execution_time_ms: 14.2,
          success: true,
        },
      ],
      action_proposal: null,
    }
    vi.spyOn(api, 'sendChat').mockResolvedValue(mockChatResponse)

    render(<App />)

    // Esperar inicialización con U-I1
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /seleccionar usuario simulado/i })).toHaveValue('U-I1')
    })

    // Interactuar con el chat (hacer clic en la primera pregunta de ejemplo)
    const exampleQuestion = screen.getByText('¿Qué le falta a ORG-07 para pasar a producción?')
    await user.click(exampleQuestion)

    // Verificar que la respuesta se despliega con su cita documental
    await waitFor(() => {
      expect(screen.getByText('Respuesta de prueba sobre ORG-07')).toBeInTheDocument()
      expect(screen.getByText('GUI-INC_v2')).toBeInTheDocument()
    })

    // Verificar que el panel de trazas MCP se actualizó con la traza de la respuesta
    await waitFor(() => {
      expect(screen.getByText('consultar_integracion')).toBeInTheDocument()
      expect(screen.getByText('14,2 ms')).toBeInTheDocument()
    })

    // Cambiar sesión a U-I2
    const select = screen.getByRole('combobox', { name: /seleccionar usuario simulado/i })
    await user.selectOptions(select, 'U-I2')

    // Al cambiar la sesión, el chat y las trazas deben haberse limpiado
    await waitFor(() => {
      expect(screen.queryByText('Respuesta de prueba sobre ORG-07')).not.toBeInTheDocument()
      expect(screen.getByText('¿Qué le falta a ORG-07 para pasar a producción?')).toBeInTheDocument()
      expect(screen.getByText('Aún sin consultas')).toBeInTheDocument()
      expect(screen.queryByText('consultar_integracion')).not.toBeInTheDocument()
    })
  })

  it('abre el modal de confirmación de acción cuando la respuesta del chat contiene una action_proposal', async () => {
    const user = userEvent.setup()
    const mockProposalChatResponse: ChatResponse = {
      answer: 'Propuesta generada para completar T-006',
      citations: [],
      evidence_status: 'COMPLETA',
      mcp_traces: [],
      action_proposal: {
        action_type: 'CAMBIO_ESTADO_TAREA',
        tarea_id: 'T-006',
        org_id: 'ORG-05',
        estado_actual: 'en_curso',
        estado_propuesto: 'completada',
        justificacion: 'Se verificó recepción SFTP.',
        confirmation_token: 'secret-token-demo',
        expires_at: '2026-11-07T12:05:00Z',
      },
    }
    vi.spyOn(api, 'sendChat').mockResolvedValue(mockProposalChatResponse)

    render(<App />)

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /seleccionar usuario simulado/i })).toHaveValue('U-I1')
    })

    const questionBtn = screen.getByText('¿Qué le falta a ORG-07 para pasar a producción?')
    await user.click(questionBtn)

    // Modal debe abrirse automáticamente con la propuesta
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /confirmación de acción requerida/i })).toBeInTheDocument()
      expect(screen.getByText('T-006')).toBeInTheDocument()
      expect(screen.getByText('Se verificó recepción SFTP.')).toBeInTheDocument()
    })
  })

  it('invalida respuestas pendientes al cambiar de sesión y no actualiza trazas, mensajes ni modal', async () => {
    const user = userEvent.setup()
    let resolveDeferredChat!: (value: ChatResponse) => void
    const deferredChatPromise = new Promise<ChatResponse>((resolve) => {
      resolveDeferredChat = resolve
    })

    const sendChatSpy = vi.spyOn(api, 'sendChat').mockImplementation(() => deferredChatPromise)

    render(<App />)

    // Esperar inicialización en U-I1
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: /seleccionar usuario simulado/i })).toHaveValue('U-I1')
    })

    // Enviar consulta como U-I1 usando una pregunta de ejemplo
    const exampleQuestion = screen.getByText('¿Qué le falta a ORG-07 para pasar a producción?')
    await user.click(exampleQuestion)

    expect(sendChatSpy).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/El asistente está respondiendo…/i)).toBeInTheDocument()

    // Cambiar de sesión a U-I2 antes de que la promesa se resuelva
    const select = screen.getByRole('combobox', { name: /seleccionar usuario simulado/i })
    await user.selectOptions(select, 'U-I2')

    await waitFor(() => {
      expect(select).toHaveValue('U-I2')
    })

    // Resolver la promesa diferida de la consulta enviada en la sesión anterior
    const staleResponse: ChatResponse = {
      answer: 'Respuesta diferida obsoleta de U-I1',
      citations: [
        {
          chunk_id: 'GUI-INC_v2#sec3_1',
          doc_code: 'GUI-INC_v2',
          doc_title: 'Guía de Incorporación',
          section: '§3.1',
          version: 'v2',
          status: 'vigente',
          excerpt: 'Requisitos de salida a producción.',
        },
      ],
      evidence_status: 'COMPLETA',
      mcp_traces: [
        {
          tool_name: 'consultar_integracion',
          parameters: { org_id: 'ORG-07' },
          response_summary: 'Telemetría obsoleta de U-I1',
          execution_time_ms: 10.0,
          success: true,
        },
      ],
      action_proposal: {
        action_type: 'CAMBIO_ESTADO_TAREA',
        tarea_id: 'T-006',
        org_id: 'ORG-05',
        estado_actual: 'en_curso',
        estado_propuesto: 'completada',
        justificacion: 'Acción obsoleta que no debe abrirse en la sesión nueva',
        confirmation_token: 'stale-token',
        expires_at: '2026-11-08T23:59:59Z',
      },
    }

    resolveDeferredChat(staleResponse)

    // Dar tiempo para que cualquier microtarea o callback pendiente se procese
    await new Promise((r) => setTimeout(r, 50))

    // En la sesión nueva no se agregan mensajes, trazas ni modal
    expect(screen.queryByText('Respuesta diferida obsoleta de U-I1')).not.toBeInTheDocument()
    expect(screen.queryByText('Telemetría obsoleta de U-I1')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: /confirmación de acción requerida/i }),
    ).not.toBeInTheDocument()
    expect(screen.getByText('Aún sin consultas')).toBeInTheDocument()
  })
})