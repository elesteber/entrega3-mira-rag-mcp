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
})
