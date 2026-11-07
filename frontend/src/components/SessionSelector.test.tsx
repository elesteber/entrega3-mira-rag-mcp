import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { SessionSelector } from './SessionSelector'
import * as api from '../services/api'

describe('SessionSelector Component (T045)', () => {
  const mockUsers = [
    {
      usuario_id: 'U-I1',
      nombre: 'Sofía Tapia',
      rol: 'ejecutivo_implementacion' as const,
      orgs_asignadas: ['ORG-05', 'ORG-07'],
    },
    {
      usuario_id: 'U-I2',
      nombre: 'Diego Fuentes',
      rol: 'ejecutivo_implementacion' as const,
      orgs_asignadas: ['ORG-06', 'ORG-08'],
    },
  ]

  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(api, 'listUsers').mockResolvedValue(mockUsers)
    vi.spyOn(api, 'switchSession').mockImplementation(async (userId) => {
      const user = mockUsers.find((u) => u.usuario_id === userId) || mockUsers[0]
      return {
        session_token: `token-${user.usuario_id}`,
        user,
        expires_at: '2026-11-07T15:00:00Z',
      }
    })
    vi.spyOn(api, 'setSessionToken').mockImplementation(() => {})
  })

  it('al montarse llama a listUsers, selecciona U-I1 por defecto y emite onSessionChange', async () => {
    const handleSessionChange = vi.fn()
    render(<SessionSelector onSessionChange={handleSessionChange} />)

    expect(screen.getByLabelText(/Usuario simulado:/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(api.listUsers).toHaveBeenCalled()
      expect(api.switchSession).toHaveBeenCalledWith('U-I1')
      expect(api.setSessionToken).toHaveBeenCalledWith('token-U-I1')
      expect(handleSessionChange).toHaveBeenCalledWith(
        expect.objectContaining({ usuario_id: 'U-I1', nombre: 'Sofía Tapia' }),
      )
    })

    // Muestra datos del usuario activo
    expect(screen.getByText('Sofía Tapia')).toBeInTheDocument()
    expect(screen.getByText('Ejecutivo de implementación')).toBeInTheDocument()
    expect(screen.getByText('ORG-05, ORG-07')).toBeInTheDocument()

    // Aviso visible y discreto
    expect(
      screen.getByText(/Sesión simulada solo para demostración académica; no es autenticación real./i),
    ).toBeInTheDocument()
  })

  it('al cambiar de usuario ejecuta switchSession y notifica al padre con el nuevo usuario', async () => {
    const handleSessionChange = vi.fn()
    const user = userEvent.setup()

    render(<SessionSelector onSessionChange={handleSessionChange} />)

    await waitFor(() => {
      expect(screen.getByText('Sofía Tapia')).toBeInTheDocument()
    })

    const select = screen.getByLabelText(/Usuario simulado:/i)
    await user.selectOptions(select, 'U-I2')

    await waitFor(() => {
      expect(api.switchSession).toHaveBeenCalledWith('U-I2')
      expect(api.setSessionToken).toHaveBeenCalledWith('token-U-I2')
      expect(handleSessionChange).toHaveBeenCalledWith(
        expect.objectContaining({ usuario_id: 'U-I2', nombre: 'Diego Fuentes' }),
      )
      expect(screen.getByText('Diego Fuentes')).toBeInTheDocument()
      expect(screen.getByText('ORG-06, ORG-08')).toBeInTheDocument()
    })
  })

  it('maneja y muestra estado de error en caso de fallo al inicializar', async () => {
    vi.spyOn(api, 'listUsers').mockRejectedValueOnce(
      new Error('Falla al conectar con el servidor de sesiones'),
    )

    render(<SessionSelector />)

    await waitFor(() => {
      expect(
        screen.getByText(/Falla al conectar con el servidor de sesiones/i),
      ).toBeInTheDocument()
    })
  })
})

