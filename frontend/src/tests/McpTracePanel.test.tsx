import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { McpTracePanel } from '../components/McpTracePanel'
import type { McpTrace } from '../types'

describe('McpTracePanel Component (T052)', () => {
  it('(1) muestra nombre de herramienta, parámetros en JSON, response_summary, tiempo de ejecución y marca de éxito o error', () => {
    // Fixture sintético de trazas exitosa y fallida con herramientas autorizadas
    const syntheticTraces: McpTrace[] = [
      {
        tool_name: 'checklist_organizacion',
        parameters: { org_id: 'ORG-05' },
        response_summary: '10 tareas encontradas (5 completadas)',
        execution_time_ms: 14.2,
        success: true,
      },
      {
        tool_name: 'consultar_integracion',
        parameters: { org_id: 'ORG-05', sistema: 'SFTP' },
        response_summary: 'Conexión rechazada por timeout',
        execution_time_ms: 25.8,
        success: false,
        error: 'Conexión rechazada',
      },
    ]

    render(<McpTracePanel traces={syntheticTraces} />)

    // Primera traza (éxito): abierta por defecto
    expect(screen.getByText('checklist_organizacion')).toBeInTheDocument()
    expect(screen.getByText('14,2 ms')).toBeInTheDocument()
    expect(screen.getByText('Éxito')).toBeInTheDocument()
    expect(screen.getByText('10 tareas encontradas (5 completadas)')).toBeInTheDocument()

    const preJson = screen.getByText(/"org_id": "ORG-05"/i)
    expect(preJson.tagName.toLowerCase()).toBe('pre')

    // Segunda traza (error)
    expect(screen.getByText('consultar_integracion')).toBeInTheDocument()
    expect(screen.getByText('25,8 ms')).toBeInTheDocument()
    expect(screen.getByText('Error')).toBeInTheDocument()
  })

  it('(2) muestra el estado vacío "Aún sin consultas"', () => {
    render(<McpTracePanel traces={[]} />)

    expect(screen.getByRole('heading', { level: 2, name: 'Trazas MCP' })).toBeInTheDocument()
    expect(screen.getByText('Aún sin consultas')).toBeInTheDocument()
  })

  it('(3) un parámetro o resumen que contenga etiquetas HTML se muestra como texto plano y no se inserta como elemento', () => {
    // Fixture sintético con carga XSS / etiquetas HTML en parámetro y response_summary
    const syntheticXssTraces: McpTrace[] = [
      {
        tool_name: 'buscar_reglas',
        parameters: { query: '<img src=x onerror=alert(1)>' },
        response_summary: '<img src=x onerror=alert(1)> Resultado con HTML',
        execution_time_ms: 12.0,
        success: true,
      },
    ]

    const { container } = render(<McpTracePanel traces={syntheticXssTraces} />)

    // No debe haber elementos <img> creados en el DOM
    const imgElements = container.querySelectorAll('img')
    expect(imgElements.length).toBe(0)

    // Las etiquetas deben estar presentes de forma literal como texto plano
    const matchingElements = screen.getAllByText((content) =>
      content.includes('<img src=x onerror=alert(1)>'),
    )
    expect(matchingElements.length).toBe(2) // Tanto en <pre> de parámetros como en <p> de response_summary
    expect(
      screen.getByText((content) => content.includes('Resultado con HTML')),
    ).toBeInTheDocument()
  })
})
