// Auto-generated TypeScript types from backend/api/schema.py
// Do not edit manually - run: python tools/gen_ts_schema.py

export interface ActLoopDoneEvent {
  done?: boolean;
  total_steps?: number;
  reflected?: boolean;
  player?: PlayerPublic | null;
  npcs_here?: NpcBrief[] | null;
}

export interface ActLoopStepEvent {
  step: number;
  action: string;
  description?: string | null;
  success?: boolean | null;
  chunk?: string | null;
  done?: boolean;
}

export interface ActStepResult {
  action: string;
  description: string;
  success: boolean;
}

export interface AdminCircuitBreakerResponse {
  state?: string;
  total_requests?: number;
  total_failures?: number;
  rejected?: number;
  recent_failures?: number;
  last_failure_age_s?: number | null;
}

export interface AdminEvalResponse {
  parse_success_rate?: number;
  common_violations?: any[];
  by_npc?: Record<string, any>;
}

export interface AdminMetricsResponse {
  total_calls?: number;
  success_rate?: number;
  avg_latency_ms?: number;
  p50_latency_ms?: number;
  p95_latency_ms?: number;
  total_tokens_in?: number;
  total_tokens_out?: number;
  by_operation?: Record<string, any>;
  circuit_breaker?: Record<string, any>;
}

export interface AdminNpcStateEntry {
  pos?: any;
  state?: string;
  plan_summary?: string;
}

export interface AdminNpcStatesResponse {
}

export interface AdminPlayerBrief {
  player_id: string;
  display_name: string;
  map_id: string;
  px: number;
  py: number;
  dead: boolean;
  ended: boolean;
}

export interface AdminPlayersResponse {
  players: AdminPlayerBrief[];
}

export interface AdminRecentCallsResponse {
  calls?: any[];
}

export interface AgentActLoopResponse {
  steps: ActStepResult[];
  total_steps: number;
  reflected?: boolean;
  player: PlayerPublic;
}

export interface AgentActResponse {
  action: string;
  description: string;
  success: boolean;
  mind_summary?: string;
  player: PlayerPublic;
  npcs_here: NpcBrief[];
}

export interface AgentMindItem {
}

export interface AgentMindResponse {
  npc_id: string;
  npc_name: string;
  items?: any[];
  importance_since_reflect?: number;
  plan_day?: number | null;
  plan_summary?: string;
  plan_by_shichen?: Record<string, any>;
  affect_valence?: number;
  affect_arousal?: number;
  affect_mood?: string;
  affect_cause?: string;
}

export interface AgentPlanResponse {
  ok: boolean;
  plan_day?: number | null;
  plan_summary?: string;
  plan_by_shichen?: Record<string, any>;
  player: PlayerPublic;
}

export interface AgentReflectResponse {
  added?: any[];
  count?: number;
  player: PlayerPublic;
}

export interface BountyAbandonResponse {
  ok: boolean;
  message?: string;
  player: PlayerPublic;
}

export interface BountyAcceptResponse {
  ok: boolean;
  message?: string;
  player: PlayerPublic;
}

export interface BountyCheckResponse {
  has_active: boolean;
  player: PlayerPublic;
}

export interface BountyCompleteResponse {
  ok: boolean;
  message?: string;
  reward?: any;
  player: PlayerPublic;
}

export interface BountyRefreshResponse {
  bounties?: any[];
  board_text?: string;
  player: PlayerPublic;
}

export interface BountyStateResponse {
  bounty_id: string;
  state: string;
  sub_steps?: any[];
  completed_steps?: any[];
  transition_log?: any[];
}

export interface DangerSense {
  alert?: string | null;
  scan?: string | null;
}

export interface DeleteSaveResponse {
  ok?: boolean;
}

export interface FinaleResponse {
  ending_label: string;
  epilogue?: string | null;
  flags?: Record<string, number>;
  player: PlayerPublic;
  server_ms?: number;
  already?: boolean | null;
}

export interface ForcedEncounter {
  npc_id: string;
  user_line?: string;
  blurb?: string;
}

export interface GameEvent {
  day?: number | null;
  shichen?: string | null;
  text?: string;
  scope?: string | null;
  actor?: string | null;
}

export interface HealthResponse {
  status?: string;
  llm_configured?: string;
  shutdown_configured?: string;
  world?: string;
}

export interface InitResponse {
  player_id: string;
  display_name: string;
  world_name: string;
  intro: string;
  maps: Record<string, MapData>;
  npc_catalog: any[];
  player: PlayerPublic;
  npcs_here: NpcBrief[];
  danger_sense: DangerSense;
  flags?: Record<string, number>;
  ended?: boolean;
  ending_label?: string | null;
  favor?: Record<string, number>;
  rumors?: any[];
  npc_labels?: Record<string, string>;
  ambush_markers?: any[];
  factions?: Record<string, string>;
  map_locations?: Record<string, Record<string, number[]>>;
  events?: any[];
}

export interface InteractiveModuleInfoResponse {
  id: string;
  label: string;
  icon: string;
  count: number;
  tests: InteractiveTestInfoResponse[];
}

export interface InteractiveModuleResultResponse {
  module_id: string;
  total: number;
  passed: number;
  failed: number;
  results: InteractiveTestResultResponse[];
}

export interface InteractiveModulesResponse {
  count: number;
  modules: InteractiveModuleInfoResponse[];
}

export interface InteractiveTestInfoResponse {
  name: string;
  description: string;
  module_id: string;
}

export interface InteractiveTestResultResponse {
  test_name: string;
  success: boolean;
  output: string;
  elapsed?: number;
  npc_reply?: string;
  favor_delta?: number;
  coin_delta?: number;
  dialogue_log?: any[];
}

export interface ItemUseResponse {
  success: boolean;
  note?: string;
  delta?: RestDelta | null;
  item_consumed?: string | null;
  player: PlayerPublic;
}

export interface JournalNpcHistory {
  npc_id: string;
  npc_name: string;
  turns?: any[];
}

export interface JournalResponse {
  history: JournalNpcHistory[];
  events?: any[];
  rumors?: any[];
}

export interface MapData {
  name: string;
  rows?: string[];
  portals?: any[];
}

export interface ModuleInfoResponse {
  id: string;
  label: string;
  count: number;
  tests: TestInfoResponse[];
}

export interface ModuleResultResponse {
  module_id: string;
  total: number;
  passed: number;
  failed: number;
  skipped?: number;
  results: TestResultResponse[];
}

export interface MoveDelta {
  vigor?: number;
  spirit?: number;
}

export interface MoveResponse {
  player: PlayerPublic;
  npcs_here: NpcBrief[];
  danger_sense: DangerSense;
  path_map_id: string;
  path: number[][];
  forced_encounter?: ForcedEncounter | null;
  trap_state: TrapStatePublic;
  delta: MoveDelta;
  injuries?: string[];
  atmosphere?: string;
  events?: any[];
  npc_catalog?: any[];
  map_locations?: Record<string, Record<string, number[]>>;
  respawn_msg?: string | null;
}

export interface NpcBrief {
  id: string;
  name: string;
}

export interface NpcCatalogEntry {
  id: string;
  name: string;
  map: string;
  x: number;
  y: number;
}

export interface PlayerPublic {
  map_id?: string;
  px?: number;
  py?: number;
  coins?: number;
  gender?: string;
  permadeath?: boolean;
  dead?: boolean;
  death_reason?: string | null;
  ended?: boolean;
  ending_label?: string | null;
  move_locked?: boolean;
  move_lock_npc_id?: string | null;
  trap_reason?: string | null;
  trap_attempts?: number;
  trap_type?: string | null;
  enslaved?: boolean;
  enslaved_reason?: string | null;
  vigor?: number;
  vigor_max?: number;
  spirit?: number;
  spirit_max?: number;
  sleep_debt?: number;
  unconscious_ticks?: number;
  rescue_needed?: boolean;
  life_burn_ticks?: number;
  life_burn_max?: number;
  world_day?: number;
  world_shichen_idx?: number;
  world_shichen?: string;
  world_phase?: string;
  world_is_night?: boolean;
  weather?: string;
  inventory?: Record<string, number>;
  reputation?: Record<string, number>;
  npc_states?: Record<string, string>;
  bounties?: any[];
  active_bounty?: any;
  completed_bounties?: any[];
  flags?: Record<string, number>;
  favor?: Record<string, number>;
}

export interface ResetCircuitBreakerResponse {
  status?: string;
  state?: string;
}

export interface RestDelta {
  vigor?: number;
  spirit?: number;
  sleep_debt?: number;
}

export interface RestResponse {
  ok: boolean;
  reason?: string;
  delta?: RestDelta | null;
  ticks_passed?: number;
  note?: string;
  player: PlayerPublic;
  npcs_here: NpcBrief[];
  danger_sense: DangerSense;
  atmosphere?: string;
  events?: any[];
}

export interface SaveResponse {
  ok?: boolean;
}

export interface SavesListResponse {
  saves?: any[];
}

export interface ShutdownResponse {
  status?: string;
  message?: string;
  hint?: string;
}

export interface StateResponse {
  display_name?: string;
  player: PlayerPublic;
  npcs_here: NpcBrief[];
  danger_sense: DangerSense;
  flags?: Record<string, number>;
  ended?: boolean;
  ending_label?: string | null;
  favor?: Record<string, number>;
  rumors?: any[];
  atmosphere?: string;
  events?: any[];
  factions?: Record<string, string>;
  npc_catalog?: any[];
  map_locations?: Record<string, Record<string, number[]>>;
}

export interface TalkDelta {
  coins?: number;
  items_gain?: string[];
  items_lose?: string[];
  rep?: Record<string, number>;
  favor?: number;
  events?: any[];
  vigor?: number;
  spirit?: number;
}

export interface TalkResponse {
  visible_text?: string;
  reply?: string;
  flags?: Record<string, number>;
  favor?: Record<string, number>;
  rumors?: any[];
  events?: any[];
  player: PlayerPublic;
  npcs_here: NpcBrief[];
  atmosphere?: string;
  delta: TalkDelta;
  trap_resolution?: any;
  server_ms?: number;
  llm_fallback?: boolean | null;
}

export interface TalkStreamChunkEvent {
  chunk: string;
}

export interface TalkStreamDoneEvent {
  done?: boolean;
  interrupted?: boolean | null;
  error?: string | null;
  player?: PlayerPublic;
  npcs_here?: NpcBrief[];
  delta?: TalkDelta;
  flags?: Record<string, number>;
  favor?: Record<string, number>;
  rumors?: any[];
  events?: any[];
  atmosphere?: string;
  server_ms?: number;
  llm_fallback?: boolean | null;
}

export interface TestInfoResponse {
  name: string;
  description: string;
  file_path: string;
}

export interface TestListResponse {
  count: number;
  tests: TestInfoResponse[];
}

export interface TestModulesResponse {
  count: number;
  modules: ModuleInfoResponse[];
}

export interface TestResultResponse {
  test_name: string;
  success: boolean;
  output: string;
  exit_code?: number | null;
  elapsed?: number;
  cases_passed?: number;
  cases_failed?: number;
  cases_skipped?: number;
}

export interface TrapStatePublic {
  active?: boolean;
  reason?: string | null;
  attempts?: number;
  type?: string | null;
}

export interface WaitResponse {
  ok?: boolean;
  note?: string;
  ticks_passed?: number;
  unconscious?: boolean;
  player: PlayerPublic;
  npcs_here: NpcBrief[];
  danger_sense: DangerSense;
  atmosphere?: string;
  events?: any[];
}
