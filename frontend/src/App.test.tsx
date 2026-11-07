import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import App from './App'

describe('App', () => {
  it('renderiza el título del asistente', () => {
    render(<App />)
    expect(screen.getByText('MIRA · Asistente de incorporación')).toBeInTheDocument()
  })

  it('muestra el aviso visible de datos simulados en modo mock', () => {
    render(<App />)
    expect(screen.getByText('Datos simulados')).toBeInTheDocument()
  })
})
