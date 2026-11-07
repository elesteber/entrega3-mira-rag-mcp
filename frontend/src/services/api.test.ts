import { describe, it, expect, beforeEach } from 'vitest'
import {
  listUsers,
  switchSession,
  sendChat,
  prepareAction,
  confirmAction,
  setSessionToken,
  getSessionToken,
  ApiClientError,
} from './api'
import { setMockActiveUserId } from './mocks'

describe('Servicios API y Mocks (T015)', () => {
  beforeEach(async () => {
    setSessionToken(null)
    setMockActiveUserId('U-I1')
  })

  it('listUsers retorna los 4 usuarios reales del kit', async () => {
    const users = await listUsers()
    expect(users).toHaveLength(4)
    expect(users.map((u) => u.usuario_id)).toEqual(['U-I1', 'U-I2', 'U-I3', 'U-I4'])
  })

  it('switchSession emite token de sesión en memoria sin exponerlo en localStorage', async () => {
    const session = await switchSession('U-I1')
    expect(session.user.usuario_id).toBe('U-I1')
    expect(session.session_token).toBe('mock-session-token-U-I1')
    expect(getSessionToken()).toBe('mock-session-token-U-I1')
  })

  it('Caso 1: Diagnóstico ORG-07 retorna evidencia COMPLETA con 3 citas literales', async () => {
    await switchSession('U-I1')
    const response = await sendChat({ message: '¿Qué le falta a la organización ORG-07 para pasar a producción?' })
    expect(response.evidence_status).toBe('COMPLETA')
    expect(response.citations.length).toBeGreaterThanOrEqual(3)
    expect(response.citations.map((c) => c.chunk_id)).toContain('GUI-INC-V2-SEC3-P1')
    expect(response.citations.map((c) => c.chunk_id)).toContain('REQ-INT-V2-SEC5-P1')
    expect(response.citations.map((c) => c.chunk_id)).toContain('POL-FOR-V1-SEC2-P1')
  })

  it('Caso 2: Umbral PLA-ADM retorna CONFLICTO_FUENTES (85 vs 80)', async () => {
    await switchSession('U-I1')
    const response = await sendChat({ message: '¿Cuál es el umbral de aprobación para PLA-ADM?' })
    expect(response.evidence_status).toBe('CONFLICTO_FUENTES')
    expect(response.answer).toContain('85')
    expect(response.answer).toContain('80')
    expect(response.citations[0].chunk_id).toBe('FIC-PLA-V1-SEC2-P4')
  })

  it('Caso 3: Consulta fuera del corpus declara ABSTENCION explícita', async () => {
    await switchSession('U-I1')
    const response = await sendChat({ message: '¿Cuáles son las tarifas comerciales del servicio?' })
    expect(response.evidence_status).toBe('ABSTENCION')
    expect(response.citations).toHaveLength(0)
  })

  it('Caso 4: Checklist ORG-05 retorna las 10 tareas efectivas', async () => {
    await switchSession('U-I1')
    const response = await sendChat({ message: 'Muestra el checklist de tareas de ORG-05' })
    expect(response.evidence_status).toBe('COMPLETA')
    expect(response.answer).toContain('10 tareas efectivas')
    expect(response.mcp_traces[0].tool_name).toBe('checklist_organizacion')
  })

  it('Caso 5: Propuesta de cambio de T-006 incluye action_proposal', async () => {
    await switchSession('U-I1')
    const response = await sendChat({ message: 'Quiero marcar la tarea T-006 como completada' })
    expect(response.action_proposal).toBeDefined()
    expect(response.action_proposal?.tarea_id).toBe('T-006')
    expect(response.action_proposal?.estado_propuesto).toBe('completada')
  })

  it('Caso 6: T-008 contiene observación y la reporta como dato no confiable', async () => {
    await switchSession('U-I1')
    const response = await sendChat({ message: 'Revisa la tarea T-008' })
    expect(response.answer).toContain('dato no confiable')
    expect(response.citations[0].chunk_id).toBe('GUI-INC-V2-SEC3-P2')
  })

  it('Caso 7: U-I1 consultando ORG-06 lanza 403 FORBIDDEN_ORGANIZATION_ACCESS', async () => {
    await switchSession('U-I1')
    await expect(sendChat({ message: 'Consulta las tareas de ORG-06' })).rejects.toThrowError(
      ApiClientError,
    )
    try {
      await sendChat({ message: 'Consulta las tareas de ORG-06' })
    } catch (err) {
      const apiErr = err as ApiClientError
      expect(apiErr.code).toBe('FORBIDDEN_ORGANIZATION_ACCESS')
      expect(apiErr.status).toBe(403)
      expect(apiErr.principleViolated).toBe('PR-7')
    }
  })

  it('Caso 8: U-I1 intentando marcar T-030 lanza 403 por rol', async () => {
    await switchSession('U-I1')
    await expect(prepareAction({ tarea_id: 'T-030', nuevo_estado: 'completada', justificacion: 'Prueba' })).rejects.toThrowError(
      ApiClientError,
    )
    try {
      await prepareAction({ tarea_id: 'T-030', nuevo_estado: 'completada', justificacion: 'Prueba' })
    } catch (err) {
      const apiErr = err as ApiClientError
      expect(apiErr.code).toBe('FORBIDDEN_ROLE_ACTION')
      expect(apiErr.status).toBe(403)
      expect(apiErr.principleViolated).toBe('PR-7')
    }
  })

  it('Caso 9: Mensaje con palabra falla lanza error de servicio no disponible', async () => {
    await switchSession('U-I1')
    await expect(sendChat({ message: 'Simular falla del sistema' })).rejects.toThrowError(
      'El servicio no está disponible en este momento. Intenta nuevamente en unos minutos.',
    )
  })

  it('Flujo prepareAction y confirmAction ejecuta mutación mock', async () => {
    await switchSession('U-I1')
    const prep = await prepareAction({
      tarea_id: 'T-006',
      nuevo_estado: 'completada',
      justificacion: 'Se verificó recepción SFTP',
    })
    expect(prep.proposal.tarea_id).toBe('T-006')

    const conf = await confirmAction(prep.proposal.confirmation_token)
    expect(conf.success).toBe(true)
    expect(conf.tarea_id).toBe('T-006')
    expect(conf.nuevo_estado).toBe('completada')
  })
})