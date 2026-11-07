import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ChatInterface } from '../components/ChatInterface'
import * as api from '../services/api'
import type { ChatResponse } from '../types'

describe('Checklist Component (T025)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renderiza listado de tareas en Markdown y porcentaje de progreso con badge de evidencia', async () => {
    // Fixture sintético representativo de checklist según T025 y contrato api-rest.yaml
    const syntheticChecklistResponse: ChatResponse = {
      answer: `### Checklist de Incorporación - ORG-05
Progreso de tareas: 60% completado (6 de 10)

- [x] Configuración de credenciales de integración
- [x] Firma de términos del servicio
- [ ] Validación de certificados SSL`,
      citations: [
        {
          chunk_id: 'GUI-INC_v2#sec4',
          doc_code: 'GUI-INC',
          doc_title: 'Guía de Incorporación',
          section: '§4',
          version: 'v2',
          status: 'vigente',
          excerpt: 'La organización debe completar las tareas de incorporación requeridas antes de pasar a producción.',
        },
      ],
      mcp_traces: [
        {
          tool_name: 'checklist_organizacion',
          parameters: { org_id: 'ORG-05' },
          response_summary: '10 tareas encontradas (6 completadas)',
          execution_time_ms: 15.5,
          success: true,
        },
      ],
      evidence_status: 'COMPLETA',
      action_proposal: null,
    }

    vi.spyOn(api, 'sendChat').mockResolvedValue(syntheticChecklistResponse)
    const user = userEvent.setup()

    render(<ChatInterface organizationContext="ORG-05" />)

    const textarea = screen.getByPlaceholderText(/Pregunta sobre criterios de salida/i)
    await user.type(textarea, '¿Cuál es el checklist de ORG-05?')

    const sendBtn = screen.getByRole('button', { name: /Enviar/i })
    await user.click(sendBtn)

    await waitFor(() => {
      // 1. Verifica que la lista se renderiza como elementos de lista (<li>)
      const listItems = screen.getAllByRole('listitem')
      expect(listItems.length).toBeGreaterThanOrEqual(3)
      expect(screen.getByText(/Configuración de credenciales de integración/i)).toBeInTheDocument()
      expect(screen.getByText(/Firma de términos del servicio/i)).toBeInTheDocument()
      expect(screen.getByText(/Validación de certificados SSL/i)).toBeInTheDocument()

      // 2. Verifica que el porcentaje aparece en pantalla
      expect(screen.getByText(/60%/i)).toBeInTheDocument()
      expect(screen.getByText(/Progreso de tareas: 60% completado/i)).toBeInTheDocument()

      // 3. Verifica que se muestra el badge de evidence_status
      expect(screen.getByText('Respuesta con evidencia')).toBeInTheDocument()
    })
  })
})

