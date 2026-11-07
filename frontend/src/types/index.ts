/**
 * Tipos TypeScript derivados de contracts/api-rest.yaml
 * Caso de Uso CU-3: Asistente de Incorporación de Organizaciones (MIRA)
 */

export type Role = 'ejecutivo_implementacion' | 'jefe_implementacion' | 'comercial'

export type TaskState = 'pendiente' | 'en_curso' | 'completada'

export type EvidenceStatus = 'COMPLETA' | 'PARCIAL' | 'ABSTENCION' | 'CONFLICTO_FUENTES'

export interface SimulatedUser {
  usuario_id: string
  nombre: string
  rol: Role
  orgs_asignadas: string[]
}

export interface SessionTokenResponse {
  session_token: string
  user: SimulatedUser
  expires_at: string
}

export interface HistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatRequest {
  message: string
  organization_context?: string | null
  conversation_history?: HistoryMessage[]
}

export interface Citation {
  chunk_id: string
  doc_code: string
  doc_title: string
  section: string
  version: string
  status: 'vigente' | 'derogada' | 'en_revision'
  excerpt: string
}

export interface McpTrace {
  tool_name: string
  parameters: Record<string, unknown>
  response_summary?: string
  execution_time_ms: number
  success: boolean
  error?: string | null
}

export interface ActionProposal {
  action_type: 'CAMBIO_ESTADO_TAREA' | string
  tarea_id: string
  org_id: string
  estado_actual: TaskState
  estado_propuesto: TaskState
  justificacion: string
  confirmation_token: string
  expires_at: string
}

export interface ChatResponse {
  answer: string
  citations: Citation[]
  mcp_traces: McpTrace[]
  evidence_status: EvidenceStatus
  action_proposal?: ActionProposal | null
}

export interface ActionPrepareRequest {
  tarea_id: string
  nuevo_estado: TaskState
  justificacion: string
}

export interface ActionPrepareResponse {
  proposal: ActionProposal
}

export interface ActionConfirmRequest {
  confirmation_token: string
}

export interface ActionConfirmResponse {
  success: boolean
  evento_id: number
  tarea_id: string
  org_id: string
  nuevo_estado: TaskState
  usuario_id: string
  justificacion?: string | null
  fecha_cambio: string
}

export interface ApiError {
  code: string
  message: string
  principle_violated?: string | null
  details?: Record<string, unknown> | null
}

