export const LS_KEY = "qingjian_pid";

class Store {
  constructor() {
    this.state = {
      playerId: localStorage.getItem(LS_KEY),
      maps: {},
      npcCatalog: [],
      npcLabels: {},
      npcsHere: [],
      factions: {},
      ambushMarkers: [],
      player: {
        map_id: "world",
        px: 0,
        py: 0,
        coins: 0,
        gender: "未言",
        permadeath: false,
        dead: false,
        death_reason: null,
        move_locked: false,
        move_lock_npc_id: null,
        trap_reason: null,
        trap_attempts: 0,
        enslaved: false,
        enslaved_reason: null,
        vigor: 80,
        vigor_max: 100,
        spirit: 80,
        spirit_max: 100,
        world_day: 1,
        world_shichen: "辰时",
        world_phase: "上午",
        world_is_night: false,
        weather: "薄阴",
        inventory: {},
        reputation: {},
      },
      activeNpc: "jiang",
      ended: false,
      favor: {},
      rumors: [],
      events: [],
      lastInjuryEvents: [],
      lastRouteOverlay: null,
      atmosphere: "",
      flags: { order: 0, truth: 0, hope: 0, chaos: 0 },
      worldTitle: "",
      intro: "",
      endingLabel: "",
    };
    this.listeners = new Set();
  }

  getState() {
    return this.state;
  }

  setState(newState) {
    this.state = { ...this.state, ...newState };
    this.notify();
  }

  updatePlayer(playerData) {
    if (!playerData) return;
    this.setState({ player: { ...this.state.player, ...playerData } });
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify() {
    for (const listener of this.listeners) {
      listener(this.state);
    }
  }
}

export const store = new Store();
