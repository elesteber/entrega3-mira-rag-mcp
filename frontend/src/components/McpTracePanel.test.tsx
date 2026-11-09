import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import { McpTracePanel } from './McpTracePanel'
import type { McpTrace } from '../types'

describe('McpTracePanel Component (T054)', () => {
  it('estado vacío: muestra el título "Trazas MCP" y el texto "Aún sin consultas"', () => {
    render(<McpTracePanel traces={[]} />)

    expect(screen.getByRole('heading', { level: 2, name: 'Trazas MCP' })).toBeInTheDocument()
    expect(screen.getByText('Aún sin consultas')).toBeInTheDocument()
  })

  it('muestra tool_name, tiempo en formato "14,2 ms", éxito y parámetros JSON en texto plano', () => {
    const mockTraces: McpTrace[] = [
      {
        tool_name: 'checklist_organizacion',
        parameters: { org_id: 'ORG-05' },
        response_summary: '10 tareas encontradas (5 completadas)',
        execution_time_ms: 14.2,
        success: true,
      },
    ]

    render(<McpTracePanel traces={mockTraces} />)

    expect(screen.getByText('checklist_organizacion')).toBeInTheDocument()
    expect(screen.getByText('14,2 ms')).toBeInTheDocument()
    expect(screen.getByText('Éxito')).toBeInTheDocument()

    // La primera traza está abierta por defecto: muestra parameters y response_summary
    expect(screen.getByText(/10 tareas encontradas/)).toBeInTheDocument()
    const pre = screen.getByText(/"org_id": "ORG-05"/i)
    expect(pre.tagName.toLowerCase()).toBe('pre')
  })

  it('muestra marca de error y detalle de error cuando una traza falla', () => {
    const mockFailedTraces: McpTrace[] = [
      {
        tool_name: 'consultar_integracion',
        parameters: { org_id: 'ORG-99' },
        execution_time_ms: 22.5,
        success: false,
        error: 'Organización no autorizada',
      },
    ]

    render(<McpTracePanel traces={mockFailedTraces} />)

    expect(screen.getByText('consultar_integracion')).toBeInTheDocument()
    expect(screen.getByText('22,5 ms')).toBeInTheDocument()
    expect(screen.getByText('Error')).toBeInTheDocument()
    expect(screen.getByText('Organización no autorizada')).toBeInTheDocument()
  })

  it('permite colapsar y expandir cada traza individualmente', async () => {
    const user = userEvent.setup()
    const mockTraces: McpTrace[] = [
      {
        tool_name: 'buscar_reglas',
        parameters: { query: 'salida a produccion' },
        response_summary: '3 fragmentos encontrados',
        execution_time_ms: 18.0,
        success: true,
      },
    ]

    render(<McpTracePanel traces={mockTraces} />)

    const toggleButton = screen.getByRole('button', {
      name: /detalle de traza buscar_reglas/i,
    })
    expect(toggleButton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('3 fragmentos encontrados')).toBeInTheDocument()

    // Colapsar
    await user.click(toggleButton)
    expect(toggleButton).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('3 fragmentos encontrados')).not.toBeInTheDocument()

    // Expandir nuevamente
    await user.click(toggleButton)
    expect(toggleButton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('3 fragmentos encontrados')).toBeInTheDocument()
  })
})
