import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ActionConfirmationModal } from './ActionConfirmationModal'
import * as api from '../services/api'
import type { ActionProposal, ActionPrepareResponse, ActionConfirmResponse } from '../types'

describe('ActionConfirmationModal Component (T039)', () => {
  const mockProposal: ActionProposal = {
    action_type: 'CAMBIO_ESTADO_TAREA',
    tarea_id: 'T-006',
    org_id: 'ORG-05',
    estado_actual: 'en_curso',
    estado_propuesto: 'completada',
    justificacion: 'Se habilitó carpeta SFTP compartida y se verificó recepción de archivos según REQ-INT §4.1.',
    confirmation_token: 'secret-confirmation-token-never-expose',
    expires_at: '2026-11-07T12:05:00Z',
  }

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('no renderiza nada si isOpen es false o si proposal es null', () => {
    const { container: c1 } = render(
      <ActionConfirmationModal isOpen={false} proposal={mockProposal} onClose={vi.fn()} />,
    )
    expect(c1).toBeEmptyDOMElement()

    const { container: c2 } = render(
      <ActionConfirmationModal isOpen={true} proposal={null} onClose={vi.fn()} />,
    )
    expect(c2).toBeEmptyDOMElement()
  })

  it('muestra los detalles de la propuesta, impacto estimado y botón para Preparar acción', () => {
    render(
      <ActionConfirmationModal
        isOpen={true}
        proposal={mockProposal}
        onClose={vi.fn()}
      />,
    )

    // Título y advertencia de decisión humana (PR-1, PR-6)
    expect(screen.getByRole('heading', { name: /confirmación de acción requerida/i })).toBeInTheDocument()
    expect(screen.getByText(/Decisión humana obligatoria/i)).toBeInTheDocument()

    // Datos de la propuesta en texto plano
    expect(screen.getByText('T-006')).toBeInTheDocument()
    expect(screen.getByText('ORG-05')).toBeInTheDocument()
    expect(screen.getByText('en_curso')).toBeInTheDocument()
    expect(screen.getByText('completada')).toBeInTheDocument()
    expect(screen.getByText(mockProposal.justificacion)).toBeInTheDocument()

    // Impacto estimado
    expect(screen.getByText(/Impacto estimado:/i)).toBeInTheDocument()

    // Botón preparar presente
    expect(screen.getByRole('button', { name: /preparar acción/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /confirmar y ejecutar/i })).not.toBeInTheDocument()
  })

  it('flujo en dos pasos: prepara la acción, habilita confirmación y ejecuta con éxito sin exponer confirmation_token', async () => {
    const user = userEvent.setup()
    const handleClose = vi.fn()
    const handleSuccess = vi.fn()

    const prepareSpy = vi.spyOn(api, 'prepareAction').mockResolvedValueOnce({
      proposal: {
        ...mockProposal,
        confirmation_token: 'super-secret-hmac-token-12345',
      },
    } as ActionPrepareResponse)

    const confirmSpy = vi.spyOn(api, 'confirmAction').mockResolvedValueOnce({
      success: true,
      evento_id: 42,
      tarea_id: 'T-006',
      org_id: 'ORG-05',
      nuevo_estado: 'completada',
      usuario_id: 'U-I1',
      justificacion: mockProposal.justificacion,
      fecha_cambio: '2026-11-07T12:01:00Z',
    } as ActionConfirmResponse)

    const { container } = render(
      <ActionConfirmationModal
        isOpen={true}
        proposal={mockProposal}
        onClose={handleClose}
        onSuccess={handleSuccess}
      />,
    )

    // Paso 1: Hacer clic en "Preparar acción"
    const prepareBtn = screen.getByRole('button', { name: /preparar acción/i })
    await user.click(prepareBtn)

    await waitFor(() => {
      expect(prepareSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          action_type: 'CAMBIO_ESTADO_TAREA',
          target_id: 'T-006',
          payload: {
            nuevo_estado: 'completada',
            justificacion: mockProposal.justificacion,
            org_id: 'ORG-05',
          },
        }),
        expect.any(AbortSignal),
      )
    })

    // Resumen del paso 1 completado
    await waitFor(() => {
      expect(screen.getByText(/Paso 1 completado: Acción preparada/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /confirmar y ejecutar/i })).toBeInTheDocument()
    })

    // REGLA CRÍTICA: confirmation_token nunca debe aparecer en el DOM
    expect(container.innerHTML).not.toContain('super-secret-hmac-token-12345')
    expect(container.innerHTML).not.toContain('secret-confirmation-token-never-expose')

    // Paso 2: Hacer clic en "Confirmar y ejecutar"
    const confirmBtn = screen.getByRole('button', { name: /confirmar y ejecutar/i })
    await user.click(confirmBtn)

    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalledWith('super-secret-hmac-token-12345', expect.any(AbortSignal))
    })

    // Verificar resultado exitoso y notificación
    await waitFor(() => {
      expect(screen.getByText('¡Acción ejecutada y confirmada con éxito!')).toBeInTheDocument()
      expect(screen.getByText(/Evento de auditoría registrado con identificador #42\./i)).toBeInTheDocument()
    })

    expect(handleSuccess).toHaveBeenCalledWith(
      expect.objectContaining({
        success: true,
        evento_id: 42,
        tarea_id: 'T-006',
      }),
    )

    // Cerrar modal tras éxito
    const closeBtn = screen.getByRole('button', { name: /entendido y cerrar/i })
    await user.click(closeBtn)
    expect(handleClose).toHaveBeenCalled()
  })

  it('maneja errores de ApiClientError al preparar la acción', async () => {
    const user = userEvent.setup()

    vi.spyOn(api, 'prepareAction').mockRejectedValueOnce(
      new api.ApiClientError(
        'FORBIDDEN_ROLE_ACTION',
        'La tarea de salida a producción (E5) solo la marca el jefe de implementación.',
        'PR-7',
        403,
      ),
    )

    render(
      <ActionConfirmationModal
        isOpen={true}
        proposal={mockProposal}
        onClose={vi.fn()}
      />,
    )

    const prepareBtn = screen.getByRole('button', { name: /preparar acción/i })
    await user.click(prepareBtn)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
      expect(screen.getByText(/La tarea de salida a producción \(E5\) solo la marca el jefe de implementación\./i)).toBeInTheDocument()
      expect(screen.getByText(/Principio violado: PR-7/i)).toBeInTheDocument()
    })
  })

  it('maneja errores de ApiClientError al confirmar la acción', async () => {
    const user = userEvent.setup()

    vi.spyOn(api, 'prepareAction').mockResolvedValueOnce({
      proposal: {
        ...mockProposal,
        confirmation_token: 'valid-test-token',
      },
    } as ActionPrepareResponse)

    vi.spyOn(api, 'confirmAction').mockRejectedValueOnce(
      new api.ApiClientError(
        'EXPIRED_CONFIRMATION_TOKEN',
        'El token de confirmación ha expirado o ya fue utilizado.',
        'PR-6',
        400,
      ),
    )

    render(
      <ActionConfirmationModal
        isOpen={true}
        proposal={mockProposal}
        onClose={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: /preparar acción/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /confirmar y ejecutar/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /confirmar y ejecutar/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
      expect(screen.getByText(/El token de confirmación ha expirado o ya fue utilizado\./i)).toBeInTheDocument()
      expect(screen.getByText(/Principio violado: PR-6/i)).toBeInTheDocument()
    })
  })

  it('permite cancelar y cerrar el modal con el botón Cancelar o el botón de cierre', async () => {
    const user = userEvent.setup()
    const handleClose = vi.fn()

    render(
      <ActionConfirmationModal
        isOpen={true}
        proposal={mockProposal}
        onClose={handleClose}
      />,
    )

    const cancelBtn = screen.getByRole('button', { name: /cancelar/i })
    await user.click(cancelBtn)
    expect(handleClose).toHaveBeenCalledTimes(1)

    const closeIconBtn = screen.getByRole('button', { name: /cerrar modal de confirmación/i })
    await user.click(closeIconBtn)
    expect(handleClose).toHaveBeenCalledTimes(2)
  })

  it('respuesta de prepare que no coincide: muestra error y deja confirmación deshabilitada', async () => {
    const user = userEvent.setup()

    // Servidor retorna tarea u organización o estado o justificación diferente
    vi.spyOn(api, 'prepareAction').mockResolvedValueOnce({
      proposal: {
        ...mockProposal,
        tarea_id: 'T-999', // No coincide
        confirmation_token: 'fake-token',
      },
    } as ActionPrepareResponse)

    render(
      <ActionConfirmationModal
        isOpen={true}
        proposal={mockProposal}
        onClose={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: /preparar acción/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
      expect(
        screen.getByText(/Los datos de la propuesta preparada por el servidor no coinciden con la acción solicitada/i),
      ).toBeInTheDocument()
      expect(screen.getByText(/Principio violado: PR-6/i)).toBeInTheDocument()
    })

    // La confirmación no debe haberse habilitado
    expect(screen.queryByRole('button', { name: /confirmar y ejecutar/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /preparar acción/i })).toBeInTheDocument()
  })

  it('cambio de justificación invalida el token y vuelve al paso de preparación', async () => {
    const user = userEvent.setup()

    vi.spyOn(api, 'prepareAction').mockResolvedValue({
      proposal: {
        ...mockProposal,
        confirmation_token: 'token-valido-1',
      },
    } as ActionPrepareResponse)

    const { rerender } = render(
      <ActionConfirmationModal
        isOpen={true}
        proposal={mockProposal}
        onClose={vi.fn()}
      />,
    )

    // Prepara la acción
    await user.click(screen.getByRole('button', { name: /preparar acción/i }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /confirmar y ejecutar/i })).toBeInTheDocument()
    })

    // Se cambia la justificación en la propuesta
    const updatedProposal: ActionProposal = {
      ...mockProposal,
      justificacion: 'Nueva justificación ingresada tras corregir requerimientos',
    }

    rerender(
      <ActionConfirmationModal
        isOpen={true}
        proposal={updatedProposal}
        onClose={vi.fn()}
      />,
    )

    // El token preparado debe haberse descartado y el botón de confirmación ya no debe estar disponible
    expect(screen.queryByRole('button', { name: /confirmar y ejecutar/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /preparar acción/i })).toBeInTheDocument()
    expect(screen.getByText('Nueva justificación ingresada tras corregir requerimientos')).toBeInTheDocument()
  })

  it('ignora respuesta tardía tras cerrar el modal y no actualiza estado ni ejecuta', async () => {
    const user = userEvent.setup()
    let resolvePrepare!: (value: ActionPrepareResponse) => void
    const deferredPrepare = new Promise<ActionPrepareResponse>((resolve) => {
      resolvePrepare = resolve
    })

    vi.spyOn(api, 'prepareAction').mockImplementation(() => deferredPrepare)
    const handleClose = vi.fn()

    const { rerender } = render(
      <ActionConfirmationModal
        isOpen={true}
        proposal={mockProposal}
        onClose={handleClose}
      />,
    )

    await user.click(screen.getByRole('button', { name: /preparar acción/i }))

    // El usuario cierra el modal mediante el botón de la esquina (X) mientras la llamada está en vuelo
    await user.click(screen.getByRole('button', { name: /cerrar modal de confirmación/i }))
    expect(handleClose).toHaveBeenCalled()

    // Se cierra el modal en el padre
    rerender(
      <ActionConfirmationModal
        isOpen={false}
        proposal={mockProposal}
        onClose={handleClose}
      />,
    )

    // Ahora se resuelve la respuesta tardía
    resolvePrepare({
      proposal: {
        ...mockProposal,
        confirmation_token: 'late-token-never-used',
      },
    })

    await new Promise((r) => setTimeout(r, 50))

    // Al reabrir el modal, no debe haber estado preparado residual
    rerender(
      <ActionConfirmationModal
        isOpen={true}
        proposal={mockProposal}
        onClose={handleClose}
      />,
    )

    expect(screen.queryByRole('button', { name: /confirmar y ejecutar/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /preparar acción/i })).toBeInTheDocument()
  })

  it('no acepta preparación antigua si cambia la propuesta durante la petición', async () => {
    const user = userEvent.setup()
    let resolvePrepareA!: (value: ActionPrepareResponse) => void
    const deferredPrepareA = new Promise<ActionPrepareResponse>((resolve) => {
      resolvePrepareA = resolve
    })

    vi.spyOn(api, 'prepareAction').mockImplementationOnce(() => deferredPrepareA)

    const proposalA: ActionProposal = {
      ...mockProposal,
      justificacion: 'Justificación A original',
    }
    const proposalB: ActionProposal = {
      ...mockProposal,
      justificacion: 'Justificación B nueva mientras A pendiente',
    }

    const { rerender, container } = render(
      <ActionConfirmationModal
        isOpen={true}
        proposal={proposalA}
        onClose={vi.fn()}
      />,
    )

    // Iniciar preparación de A (queda pendiente)
    await user.click(screen.getByRole('button', { name: /preparar acción/i }))

    // Cambiar a propuesta B mientras la petición de A sigue en vuelo
    rerender(
      <ActionConfirmationModal
        isOpen={true}
        proposal={proposalB}
        onClose={vi.fn()}
      />,
    )

    // Resolver la respuesta tardía de A con su token
    resolvePrepareA({
      proposal: {
        ...proposalA,
        confirmation_token: 'token-de-A-obsoleto',
      },
    })

    await new Promise((r) => setTimeout(r, 50))

    // La respuesta de A debe descartarse: no debe aparecer "Confirmar y ejecutar"
    expect(screen.queryByRole('button', { name: /confirmar y ejecutar/i })).not.toBeInTheDocument()
    // El botón "Preparar acción" debe seguir presente
    expect(screen.getByRole('button', { name: /preparar acción/i })).toBeInTheDocument()
    // El token de A no debe estar en el DOM
    expect(container.innerHTML).not.toContain('token-de-A-obsoleto')
  })

  it('usa el token de la propuesta vigente tras descartar la preparación antigua', async () => {
    const user = userEvent.setup()
    let resolvePrepareA!: (value: ActionPrepareResponse) => void
    const deferredPrepareA = new Promise<ActionPrepareResponse>((resolve) => {
      resolvePrepareA = resolve
    })

    const confirmSpy = vi.spyOn(api, 'confirmAction').mockResolvedValue({
      success: true,
      evento_id: 99,
      tarea_id: 'T-006',
      org_id: 'ORG-05',
      nuevo_estado: 'completada',
      usuario_id: 'U-I1',
      justificacion: 'Justificación B nueva mientras A pendiente',
      fecha_cambio: '2026-11-07T12:01:00Z',
    } as ActionConfirmResponse)

    const proposalA: ActionProposal = {
      ...mockProposal,
      justificacion: 'Justificación A original',
    }
    const proposalB: ActionProposal = {
      ...mockProposal,
      justificacion: 'Justificación B nueva mientras A pendiente',
    }

    vi.spyOn(api, 'prepareAction')
      .mockImplementationOnce(() => deferredPrepareA)
      .mockResolvedValueOnce({
        proposal: {
          ...proposalB,
          confirmation_token: 'token-de-B-vigente',
        },
      } as ActionPrepareResponse)

    const { rerender } = render(
      <ActionConfirmationModal
        isOpen={true}
        proposal={proposalA}
        onClose={vi.fn()}
      />,
    )

    // Iniciar preparación de A y luego cambiar a B mientras A está pendiente
    await user.click(screen.getByRole('button', { name: /preparar acción/i }))

    rerender(
      <ActionConfirmationModal
        isOpen={true}
        proposal={proposalB}
        onClose={vi.fn()}
      />,
    )

    // Resolver A (debe descartarse)
    resolvePrepareA({
      proposal: {
        ...proposalA,
        confirmation_token: 'token-de-A-obsoleto',
      },
    })

    await new Promise((r) => setTimeout(r, 50))

    // Preparar B con el botón disponible
    await user.click(screen.getByRole('button', { name: /preparar acción/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /confirmar y ejecutar/i })).toBeInTheDocument()
    })

    // Confirmar: debe usar el token de B, nunca el de A
    await user.click(screen.getByRole('button', { name: /confirmar y ejecutar/i }))

    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalledWith('token-de-B-vigente', expect.any(AbortSignal))
      expect(confirmSpy).not.toHaveBeenCalledWith('token-de-A-obsoleto', expect.any(AbortSignal))
    })
  })
})
