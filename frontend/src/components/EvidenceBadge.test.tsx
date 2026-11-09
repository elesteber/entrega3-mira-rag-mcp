import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { EvidenceBadge } from './EvidenceBadge'

describe('EvidenceBadge Component (T022)', () => {
  it('renderiza COMPLETA con texto "Respuesta con evidencia" y estilo verde', () => {
    render(<EvidenceBadge status="COMPLETA" />)
    const badge = screen.getByRole('status', {
      name: /Estado de evidencia: Respuesta con evidencia/i,
    })
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveTextContent('Respuesta con evidencia')
    expect(badge.className).toContain('text-emerald-800')
  })

  it('renderiza PARCIAL con texto "Evidencia parcial" y estilo azul', () => {
    render(<EvidenceBadge status="PARCIAL" />)
    const badge = screen.getByRole('status', {
      name: /Estado de evidencia: Evidencia parcial/i,
    })
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveTextContent('Evidencia parcial')
    expect(badge.className).toContain('text-blue-800')
  })

  it('renderiza ABSTENCION con texto "Sin información en el corpus" y estilo amarillo/ámbar', () => {
    render(<EvidenceBadge status="ABSTENCION" />)
    const badge = screen.getByRole('status', {
      name: /Estado de evidencia: Sin información en el corpus/i,
    })
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveTextContent('Sin información en el corpus')
    expect(badge.className).toContain('text-amber-800')
  })

  it('renderiza CONFLICTO_FUENTES con texto "Conflicto entre fuentes" y estilo rojo', () => {
    render(<EvidenceBadge status="CONFLICTO_FUENTES" />)
    const badge = screen.getByRole('status', {
      name: /Estado de evidencia: Conflicto entre fuentes/i,
    })
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveTextContent('Conflicto entre fuentes')
    expect(badge.className).toContain('text-rose-800')
  })
})