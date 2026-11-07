import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import { CitationCard } from './CitationCard'
import type { Citation } from '../types'

describe('CitationCard Component (T033)', () => {
  const mockCitationVigente: Citation = {
    chunk_id: 'GUI-INC_v2#sec3_1',
    doc_code: 'GUI-INC_v2',
    doc_title: 'Guía de Incorporación de Organizaciones',
    section: '§3.1',
    version: 'v2',
    status: 'vigente',
    excerpt: 'Para pasar a producción (E5), la tasa de error debe ser menor al 1%.',
  }

  const mockCitationDerogada: Citation = {
    chunk_id: 'GUI-INC_v1#sec2',
    doc_code: 'GUI-INC_v1',
    doc_title: 'Guía de Incorporación Histórica',
    section: '§2',
    version: 'v1',
    status: 'derogada',
    excerpt: 'Plazo anterior de adaptación: 45 días.',
  }

  const mockCitationRevision: Citation = {
    chunk_id: 'POL-SEG_v1#sec4',
    doc_code: 'POL-SEG_v1',
    doc_title: 'Política de Seguridad de la Información',
    section: '§4',
    version: 'v1.1',
    status: 'en_revision',
    excerpt: 'Revisión en curso de auditoría anual.',
  }

  it('cerrada muestra doc_code, version, section y chip de status VIGENTE', () => {
    render(<CitationCard citation={mockCitationVigente} defaultOpen={false} />)

    expect(screen.getByText('GUI-INC_v2')).toBeInTheDocument()
    expect(screen.getByText('v2')).toBeInTheDocument()
    expect(screen.getByText('§3.1')).toBeInTheDocument()
    expect(screen.getByText('VIGENTE')).toBeInTheDocument()

    // No debe mostrar excerpt ni chunk_id al estar cerrada
    expect(screen.queryByText('GUI-INC_v2#sec3_1')).not.toBeInTheDocument()
    expect(
      screen.queryByText(/Para pasar a producción \(E5\)/i),
    ).not.toBeInTheDocument()
  })

  it('muestra chip DEROGADA en cita con status derogada', () => {
    render(<CitationCard citation={mockCitationDerogada} defaultOpen={false} />)
    expect(screen.getByText('DEROGADA')).toBeInTheDocument()
  })

  it('muestra chip EN REVISIÓN en cita con status en_revision', () => {
    render(<CitationCard citation={mockCitationRevision} defaultOpen={false} />)
    expect(screen.getByText('EN REVISIÓN')).toBeInTheDocument()
  })

  it('abierta muestra chunk_id, doc_title y excerpt en un bloque de cita en texto plano', () => {
    render(<CitationCard citation={mockCitationVigente} defaultOpen={true} />)

    expect(screen.getByText('GUI-INC_v2#sec3_1')).toBeInTheDocument()
    expect(
      screen.getByText('Guía de Incorporación de Organizaciones'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Para pasar a producción (E5), la tasa de error debe ser menor al 1%.'),
    ).toBeInTheDocument()
  })

  it('permite alternar entre abierta y cerrada al hacer clic', async () => {
    const user = userEvent.setup()
    render(<CitationCard citation={mockCitationVigente} defaultOpen={false} />)

    const toggleButton = screen.getByRole('button', {
      name: /detalles de cita GUI-INC_v2 §3\.1/i,
    })
    expect(toggleButton).toHaveAttribute('aria-expanded', 'false')

    // Al hacer clic, se abre
    await user.click(toggleButton)
    expect(toggleButton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('GUI-INC_v2#sec3_1')).toBeInTheDocument()

    // Al hacer clic nuevamente, se cierra
    await user.click(toggleButton)
    expect(toggleButton).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('GUI-INC_v2#sec3_1')).not.toBeInTheDocument()
  })
})

