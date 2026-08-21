(() => {
  "use strict";

  const labels = {
    hunger: "饥饿",
    energy: "精力",
    mood: "心情",
    health: "健康",
    cleanliness: "清洁",
    intimacy: "亲密",
  };
  const activityNames = {
    resting: "休息中",
    eating: "吃东西",
    tired: "有点累",
    playing: "玩耍中",
    bathing: "洗澡中",
    sleeping: "睡着了",
  };
  const locationNames = { pet_home: "宠物家园" };
  const particleGlyphs = { fish: "🐟", star: "✨", bubble: "🫧", zzz: "💤" };
  // Every action is one validated POST to the domain service: the browser
  // never computes state deltas itself.
  const petActions = {
    feed: { path: "/api/pet/feed", busy: "小光正在吃小鱼干…", body: { food: "小鱼干" } },
    play: { path: "/api/pet/play", busy: "小光正在陪你玩…", body: { game: "追激光笔" } },
    clean: { path: "/api/pet/clean", busy: "小光正在洗澡…", body: { method: "洗澡" } },
    sleep: { path: "/api/pet/sleep", busy: "小光正在准备睡觉…", body: {} },
  };
  const seenReactionIds = new Set();
  const MOTION_PRIORITY_FORCE = 3;
  const INVALID_MOTION_HANDLE = -1;
  const SOUND_MUTED_KEY = "slai-pet-sound-muted";
  // Short self-authored chimes synthesised with WebAudio: no bundled audio
  // asset, therefore no third-party licence to clear.
  const SOUND_LIBRARY = {
    feed_chime: { type: "triangle", gain: 0.16, notes: [[880, 0, 0.12], [1174.66, 0.08, 0.14], [1567.98, 0.17, 0.22]] },
    play_chime: { type: "square", gain: 0.11, notes: [[659.25, 0, 0.1], [987.77, 0.09, 0.16]] },
    clean_chime: { type: "sine", gain: 0.14, notes: [[1318.51, 0, 0.1], [1760, 0.08, 0.18]] },
    sleep_chime: { type: "sine", gain: 0.12, notes: [[523.25, 0, 0.2], [392, 0.16, 0.3]] },
  };
  let currentProfile = null;
  let live2dCapabilities = null;
  let reconnectAttempt = 0;
  let reconnectTimer = null;
  let eventSocket = null;
  let audioContext = null;
  let soundMuted = false;
  let expressionRestoreTimer = null;
  let speechHideTimer = null;
  let cameraPip = null;
  let cameraStream = null;
  let cameraScanTimer = null;
  let cameraObserver = null;
  const CAMERA_SHAPES = ["wide", "circle", "hidden"];
  const CAMERA_SHAPE_LABELS = { wide: "16:9", circle: "圆形", hidden: "隐藏预览" };
  const CAMERA_STATE_KEY = "slai-pet-camera-pip";
  let worldLayer = null;
  let worldLayerFlip = false;
  let worldTimer = null;
  let currentWorldEventId = null;
  let currentBackgroundKey = null;
  let drawerPanel = null;
  let bubbleAnchorObserver = null;
  let sleepIdleTimer = null;
  let lastActivity = null;
  const recentSpeech = [];
  const RECENT_SPEECH_LIMIT = 30;
  const SPEECH_BASE_MS = 2400;
  const SPEECH_PER_CHAR_MS = 90;
  const SPEECH_MAX_MS = 12000;
  try {
    soundMuted = window.localStorage.getItem(SOUND_MUTED_KEY) === "true";
  } catch (_) {
    soundMuted = false;
  }

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function createPanel() {
    const panel = node("aside");
    panel.id = "slai-pet-panel";
    panel.setAttribute("aria-label", "宠物成长状态");

    const head = node("div", "slai-pet-head");
    head.append(node("div", "slai-pet-orb", "☀"));
    const title = node("div", "slai-pet-title");
    const name = node("strong", "", "小光");
    name.dataset.field = "name";
    const persona = node("span", "", "SLAI Pet · 正在载入状态");
    persona.dataset.field = "persona";
    title.append(name, persona);
    const drawerToggle = node("button", "slai-pet-icon-button slai-pet-drawer-toggle", "☰");
    drawerToggle.type = "button";
    drawerToggle.dataset.action = "drawer";
    drawerToggle.title = "打开最近对话与共同记忆";
    drawerToggle.setAttribute("aria-expanded", "false");
    drawerToggle.addEventListener("click", () => toggleDrawer(drawerToggle));

    const sound = node("button", "slai-pet-icon-button slai-pet-sound-toggle", soundMuted ? "🔇" : "🔊");
    sound.type = "button";
    sound.dataset.action = "sound";
    sound.title = soundMuted ? "开启反应音效" : "关闭反应音效";
    sound.setAttribute("aria-pressed", String(!soundMuted));
    sound.addEventListener("click", () => {
      soundMuted = !soundMuted;
      try {
        window.localStorage.setItem(SOUND_MUTED_KEY, String(soundMuted));
      } catch (_) {
        /* storage unavailable: keep the in-memory preference only */
      }
      sound.textContent = soundMuted ? "🔇" : "🔊";
      sound.title = soundMuted ? "开启反应音效" : "关闭反应音效";
      sound.setAttribute("aria-pressed", String(!soundMuted));
      if (!soundMuted) playReactionSound("feed_chime");
    });

    const toggle = node("button", "slai-pet-icon-button", "⌃");
    toggle.type = "button";
    toggle.title = "收起宠物状态";
    toggle.addEventListener("click", () => {
      const collapsed = panel.classList.toggle("is-collapsed");
      toggle.textContent = collapsed ? "⌄" : "⌃";
      toggle.title = collapsed ? "展开宠物状态" : "收起宠物状态";
      localStorage.setItem("slai-pet-panel-collapsed", String(collapsed));
    });
    head.append(title, drawerToggle, sound, toggle);

    const body = node("div", "slai-pet-body");
    const meta = node("div", "slai-pet-meta");
    meta.append(node("i", "slai-pet-dot"));
    const activity = node("b", "", "同步中");
    activity.dataset.field = "activity";
    const location = node("span", "", "宠物家园");
    location.dataset.field = "location";
    meta.append(activity, node("span", "", "·"), location);
    body.append(meta);

    const world = node("div", "slai-pet-world");
    world.dataset.field = "world";
    const worldHead = node("div", "slai-pet-world-head");
    const phase = node("b", "", "…");
    phase.dataset.field = "world-phase";
    const behavior = node("span", "slai-pet-world-behavior", "…");
    behavior.dataset.field = "world-behavior";
    worldHead.append(phase, behavior);
    const worldNote = node("span", "slai-pet-world-note", "");
    worldNote.dataset.field = "world-note";
    const worldRemaining = node("span", "slai-pet-world-remaining", "");
    worldRemaining.dataset.field = "world-remaining";
    world.append(worldHead, worldNote, worldRemaining);
    body.append(world);

    const stats = node("div", "slai-pet-stats");
    Object.entries(labels).forEach(([key, label]) => {
      const row = node("div", "slai-pet-stat");
      row.dataset.key = key;
      row.append(node("span", "slai-pet-stat-label", label));
      const track = node("div", "slai-pet-track");
      const fill = node("div", "slai-pet-fill");
      fill.dataset.fill = key;
      track.append(fill);
      const value = node("span", "slai-pet-stat-value", "--");
      value.dataset.value = key;
      row.append(track, value);
      stats.append(row);
    });
    body.append(stats);

    const growth = node("div", "slai-pet-growth");
    [["level", "等级"], ["experience", "经验"], ["maturity", "成长值"]].forEach(([key, label]) => {
      const item = node("div");
      const value = node("b", "", "--");
      value.dataset.field = key;
      item.append(value, node("span", "", label));
      growth.append(item);
    });
    body.append(growth);

    const tags = node("div", "slai-pet-tags");
    tags.dataset.field = "capabilities";
    body.append(tags);

    const actions = node("div", "slai-pet-actions");
    const feed = node("button", "slai-pet-feed", "喂一份小鱼干");
    feed.type = "button";
    feed.dataset.action = "feed";
    const refresh = node("button", "slai-pet-refresh", "↻");
    refresh.type = "button";
    refresh.title = "刷新状态";
    refresh.dataset.action = "refresh";
    actions.append(feed, refresh);
    body.append(actions);

    const careActions = node("div", "slai-pet-care-actions");
    [
      ["play", "陪玩", "陪小光玩一会儿"],
      ["clean", "洗澡", "给小光洗澡"],
      ["sleep", "睡觉", "让小光去睡觉"],
    ].forEach(([action, label, title]) => {
      const button = node("button", "slai-pet-care", label);
      button.type = "button";
      button.title = title;
      button.dataset.action = action;
      careActions.append(button);
    });
    body.append(careActions);

    const message = node("p", "slai-pet-message", "正在连接真实宠物状态…");
    message.dataset.field = "message";
    body.append(message);
    panel.append(head, body);

    if (localStorage.getItem("slai-pet-panel-collapsed") === "true") {
      panel.classList.add("is-collapsed");
      toggle.textContent = "⌄";
    }
    document.body.append(panel);
    return panel;
  }

  function createReactionLayer() {
    const layer = node("div", "slai-pet-reaction-layer");
    layer.setAttribute("aria-live", "polite");
    layer.setAttribute("aria-atomic", "true");
    layer.setAttribute("role", "status");
    const bubble = node("div", "slai-pet-head-bubble");
    bubble.dataset.field = "reaction-bubble";
    const text = node("span", "slai-pet-bubble-text");
    text.dataset.field = "bubble-text";
    const expand = node("button", "slai-pet-bubble-expand", "展开");
    expand.type = "button";
    expand.hidden = true;
    expand.addEventListener("click", () => {
      const expanded = bubble.classList.toggle("is-expanded");
      expand.textContent = expanded ? "收起" : "展开";
      positionReactionLayer(layer);
    });
    bubble.append(text, expand);
    layer.append(bubble);
    document.body.append(layer);
    return layer;
  }

  function setMessage(panel, text, isError = false) {
    const message = panel.querySelector('[data-field="message"]');
    message.textContent = text;
    message.dataset.error = String(isError);
  }

  function renderState(panel, state) {
    panel.querySelector('[data-field="activity"]').textContent = activityNames[state.activity] || state.activity;
    panel.querySelector('[data-field="location"]').textContent = locationNames[state.location] || state.location;
    Object.keys(labels).forEach((key) => {
      const value = Math.max(0, Math.min(100, Number(state[key]) || 0));
      panel.querySelector(`[data-fill="${key}"]`).style.width = `${value}%`;
      panel.querySelector(`[data-value="${key}"]`).textContent = Math.round(value);
    });
    panel.querySelector('[data-field="level"]').textContent = `Lv.${state.level}`;
    panel.querySelector('[data-field="experience"]').textContent = state.experience;
    panel.querySelector('[data-field="maturity"]').textContent = Math.round(state.maturity);
    syncActivityMotion(state.activity);
  }

  function render(panel, payload) {
    const { profile, state } = payload;
    currentProfile = profile;
    if (payload.live2d) live2dCapabilities = payload.live2d;
    panel.querySelector('[data-field="name"]').textContent = profile.name || "小光";
    panel.querySelector('[data-field="persona"]').textContent = `${profile.persona} · ${profile.voice || "默认音色"}`;
    renderState(panel, state);
    const tags = panel.querySelector('[data-field="capabilities"]');
    tags.replaceChildren(...profile.capabilities.map((item) => node("span", "slai-pet-tag", item)));
    setMessage(panel, `“${profile.catchphrase}” · 状态已持久化`);
  }

  // The Live2D stage owns a dedicated container in the app bundle; fall back to
  // the largest canvas only when that container is not present.
  function findLive2dCanvas() {
    const container = document.getElementById("live2d");
    const scoped = container ? container.querySelector("canvas") : null;
    const candidates = scoped ? [scoped] : [...document.querySelectorAll("canvas")];
    return candidates
      .map((canvas) => ({ canvas, rect: canvas.getBoundingClientRect() }))
      .filter(({ rect }) => rect.width > 80 && rect.height > 80)
      .sort((left, right) => right.rect.width * right.rect.height - left.rect.width * left.rect.height)[0];
  }

  // The head is not always at the centre of the canvas: the model can be moved
  // or rescaled. Use the model matrix offset as a hint, clamped so a surprising
  // value can never push the bubble off the character.
  function headAnchor(rect) {
    let verticalHint = 0;
    try {
      const adapter = getLive2dAdapter();
      const position = adapter && typeof adapter.getModelPosition === "function"
        ? adapter.getModelPosition()
        : null;
      if (position && Number.isFinite(position.y)) {
        verticalHint = Math.max(-0.35, Math.min(0.35, -position.y / 2));
      }
    } catch (_) {
      verticalHint = 0;
    }
    return {
      x: rect.left + rect.width * 0.5,
      y: rect.top + rect.height * (0.18 + verticalHint),
    };
  }

  function positionReactionLayer(layer) {
    const target = findLive2dCanvas();
    if (!target) {
      layer.style.left = "42vw";
      layer.style.top = "20vh";
      return null;
    }
    const anchor = headAnchor(target.rect);
    const width = layer.offsetWidth || 260;
    const margin = 12;
    const left = Math.min(
      Math.max(anchor.x, margin + width / 2),
      Math.max(margin + width / 2, window.innerWidth - margin - width / 2),
    );
    const top = Math.min(
      Math.max(anchor.y, 64),
      Math.max(64, window.innerHeight - 120),
    );
    layer.style.left = `${left}px`;
    layer.style.top = `${top}px`;
    watchAnchor(layer, target.canvas);
    return target.canvas;
  }

  // Keep the bubble glued to the model when the window, the sidebar or the
  // canvas itself changes size.
  function watchAnchor(layer, canvas) {
    if (bubbleAnchorObserver || typeof ResizeObserver !== "function") return;
    bubbleAnchorObserver = new ResizeObserver(() => {
      if (layer.classList.contains("is-visible")) positionReactionLayer(layer);
    });
    try {
      bubbleAnchorObserver.observe(canvas);
    } catch (_) {
      bubbleAnchorObserver = null;
    }
  }

  function getLive2dAdapter() {
    try {
      const factory = window.getLAppAdapter;
      if (typeof factory !== "function") return null;
      const adapter = factory();
      if (!adapter || typeof adapter.startMotion !== "function") return null;
      return adapter;
    } catch (_) {
      return null;
    }
  }

  function startCapabilityMotion(groupName) {
    const motions = (live2dCapabilities && live2dCapabilities.motions) || [];
    const motion = motions.find(
      (item) => String(item.group || "").toLowerCase() === groupName.toLowerCase(),
    );
    if (!motion || !Number.isInteger(motion.index)) return false;
    const adapter = getLive2dAdapter();
    if (!adapter) return false;
    try {
      const handle = adapter.startMotion(motion.group, motion.index, MOTION_PRIORITY_FORCE);
      return handle !== INVALID_MOTION_HANDLE && handle !== undefined && handle !== null;
    } catch (_) {
      return false;
    }
  }

  // Sleep is a persistent domain activity. The reaction starts Sleep once;
  // afterwards this keeps a gentle native breathing loop active. Offline
  // recovery can wake the pet without a reaction, so that transition plays
  // the native Wake motion here.
  function syncActivityMotion(activity) {
    const previous = lastActivity;
    lastActivity = activity;
    if (activity === "sleeping") {
      if (previous === null) {
        sleepIdleTimer = window.setTimeout(() => {
          if (lastActivity === "sleeping") startCapabilityMotion("SleepIdle");
        }, 600);
      } else if (previous !== "sleeping") {
        window.clearTimeout(sleepIdleTimer);
        sleepIdleTimer = window.setTimeout(() => {
          if (lastActivity === "sleeping") startCapabilityMotion("SleepIdle");
        }, 3200);
      }
      return;
    }
    if (previous === "sleeping") {
      window.clearTimeout(sleepIdleTimer);
      sleepIdleTimer = null;
      startCapabilityMotion("Wake");
    }
  }

  function expressionNameFromLabel(label) {
    if (!label || !live2dCapabilities) return null;
    const names = live2dCapabilities.expressions || [];
    const map = live2dCapabilities.emotion_map || {};
    const index = map[String(label).toLowerCase()];
    if (Number.isInteger(index) && names[index]) return names[index];
    return names.find((name) => name.toLowerCase() === String(label).toLowerCase()) || null;
  }

  function neutralExpressionName() {
    return expressionNameFromLabel("neutral");
  }

  // The server resolves reactions against the assets the model really ships.
  // When an older payload arrives without `render`, degrade to the fallback
  // expression using the capabilities reported by /api/pet/state.
  function renderPlanFor(reaction, render) {
    if (render) return render;
    const name = expressionNameFromLabel(reaction && reaction.fallback_expression);
    if (!name) return null;
    return { motion: null, expression: { name }, degraded: true, reason: "client_fallback" };
  }

  function applyLive2dRender(render, durationMs) {
    const adapter = getLive2dAdapter();
    if (!adapter) return "no-adapter";
    try {
      const motion = render && render.motion;
      if (motion && Number.isInteger(motion.index)) {
        const handle = adapter.startMotion(motion.group || "", motion.index, MOTION_PRIORITY_FORCE);
        if (handle !== INVALID_MOTION_HANDLE && handle !== undefined && handle !== null) return "motion";
      }
      const expression = render && render.expression && render.expression.name;
      if (expression && typeof adapter.setExpression === "function") {
        adapter.setExpression(expression);
        window.clearTimeout(expressionRestoreTimer);
        const restore = neutralExpressionName();
        if (restore && restore !== expression) {
          expressionRestoreTimer = window.setTimeout(() => {
            try {
              adapter.setExpression(restore);
            } catch (_) {
              /* the model may have been swapped meanwhile */
            }
          }, Math.max(600, Number(durationMs) || 3200));
        }
        return "expression";
      }
    } catch (_) {
      return "error";
    }
    return "unavailable";
  }

  function ensureAudioContext() {
    if (audioContext) return audioContext;
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return null;
    try {
      audioContext = new Ctor();
    } catch (_) {
      audioContext = null;
    }
    return audioContext;
  }

  // Never let audio failures break a reaction: autoplay policy, a missing
  // WebAudio implementation or a suspended context all degrade to silence.
  function playReactionSound(soundId) {
    if (soundMuted || !soundId) return false;
    const spec = SOUND_LIBRARY[soundId];
    if (!spec) return false;
    try {
      const context = ensureAudioContext();
      if (!context) return false;
      if (context.state === "suspended") context.resume().catch(() => {});
      if (context.state !== "running") return false;
      const startedAt = context.currentTime;
      spec.notes.forEach(([frequency, offset, length]) => {
        const oscillator = context.createOscillator();
        const envelope = context.createGain();
        oscillator.type = spec.type || "sine";
        oscillator.frequency.setValueAtTime(frequency, startedAt + offset);
        envelope.gain.setValueAtTime(0.0001, startedAt + offset);
        envelope.gain.exponentialRampToValueAtTime(spec.gain || 0.12, startedAt + offset + 0.02);
        envelope.gain.exponentialRampToValueAtTime(0.0001, startedAt + offset + length);
        oscillator.connect(envelope);
        envelope.connect(context.destination);
        oscillator.start(startedAt + offset);
        oscillator.stop(startedAt + offset + length + 0.05);
      });
      return true;
    } catch (_) {
      return false;
    }
  }

  function createDrawer() {
    const drawer = node("aside");
    drawer.id = "slai-pet-drawer";
    drawer.hidden = true;
    drawer.setAttribute("aria-label", "最近对话与共同记忆");

    const head = node("div", "slai-pet-drawer-head");
    head.append(node("strong", "", "小光的侧边栏"));
    const close = node("button", "slai-pet-icon-button", "×");
    close.type = "button";
    close.title = "收起侧边栏";
    close.addEventListener("click", () => toggleDrawer(null, false));
    head.append(close);

    const tabs = node("div", "slai-pet-drawer-tabs");
    tabs.setAttribute("role", "tablist");
    const sections = node("div", "slai-pet-drawer-sections");

    [
      ["recent", "最近对话"],
      ["memory", "共同记忆"],
    ].forEach(([key, label], index) => {
      const tab = node("button", "slai-pet-drawer-tab", label);
      tab.type = "button";
      tab.dataset.tab = key;
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-selected", String(index === 0));
      tab.addEventListener("click", () => selectDrawerTab(key));
      tabs.append(tab);

      const section = node("div", "slai-pet-drawer-section");
      section.dataset.section = key;
      section.hidden = index !== 0;
      sections.append(section);
    });

    const recent = sections.querySelector('[data-section="recent"]');
    const list = node("ul", "slai-pet-speech-list");
    list.dataset.field = "speech-list";
    recent.append(
      node("p", "slai-pet-drawer-hint", "这里显示小光刚刚说过的话，只是短期显示缓冲，不是长期记忆。"),
      list,
    );

    const memory = sections.querySelector('[data-section="memory"]');
    memory.append(
      node("div", "slai-pet-empty-state", "共同记忆还没有开始记录。"),
      node("p", "slai-pet-drawer-hint", "长期记忆需要可查看来源、可编辑、可删除的记忆对象；在它真正实现前，这里不会用聊天记录冒充记忆。"),
    );

    drawer.append(head, tabs, sections);
    document.body.append(drawer);
    return drawer;
  }

  function selectDrawerTab(key) {
    if (!drawerPanel) return;
    drawerPanel.querySelectorAll("[data-tab]").forEach((tab) => {
      tab.setAttribute("aria-selected", String(tab.dataset.tab === key));
    });
    drawerPanel.querySelectorAll("[data-section]").forEach((section) => {
      section.hidden = section.dataset.section !== key;
    });
  }

  function toggleDrawer(toggleButton, force) {
    if (!drawerPanel) return;
    const open = force === undefined ? drawerPanel.hidden : force;
    drawerPanel.hidden = !open;
    const button = toggleButton || document.querySelector('[data-action="drawer"]');
    if (button) button.setAttribute("aria-expanded", String(open));
    try {
      window.localStorage.setItem("slai-pet-drawer-open", String(open));
    } catch (_) {
      /* storage unavailable: keep the in-memory state only */
    }
  }

  function renderRecentSpeech() {
    if (!drawerPanel) return;
    const list = drawerPanel.querySelector('[data-field="speech-list"]');
    if (!list) return;
    list.replaceChildren(
      ...recentSpeech
        .slice()
        .reverse()
        .map((item) => {
          const entry = node("li", "slai-pet-speech-item");
          const time = new Date(item.occurred_at || Date.now());
          entry.append(
            node("span", "slai-pet-speech-time", Number.isNaN(time.getTime()) ? "" : time.toLocaleTimeString()),
            node("span", "slai-pet-speech-text", item.text || ""),
          );
          return entry;
        }),
    );
  }

  function rememberSpeech(message) {
    if (recentSpeech.some((item) => item.sequence === message.sequence)) return;
    recentSpeech.push(message);
    while (recentSpeech.length > RECENT_SPEECH_LIMIT) recentSpeech.shift();
    renderRecentSpeech();
  }

  async function loadRecentSpeech() {
    try {
      const response = await fetch("/api/pet/speech/recent?limit=20", { cache: "no-store" });
      if (!response.ok) return;
      const payload = await response.json();
      (payload.items || []).forEach((item) => {
        if (!recentSpeech.some((existing) => existing.sequence === item.sequence)) {
          recentSpeech.push(item);
        }
      });
      while (recentSpeech.length > RECENT_SPEECH_LIMIT) recentSpeech.shift();
      renderRecentSpeech();
    } catch (_) {
      /* the drawer is optional: never block startup on it */
    }
  }

  // --- Camera picture-in-picture -----------------------------------------
  // Privacy contract for this module: it mirrors the live MediaStream into a
  // <video> element and nothing else. It never draws a frame to a canvas,
  // never reads pixels, never uploads or stores anything.

  function readCameraState() {
    const fallback = { x: 24, y: 96, scale: 1, shape: "wide" };
    try {
      const stored = JSON.parse(window.localStorage.getItem(CAMERA_STATE_KEY) || "null");
      if (!stored || typeof stored !== "object") return fallback;
      return {
        x: Number.isFinite(stored.x) ? stored.x : fallback.x,
        y: Number.isFinite(stored.y) ? stored.y : fallback.y,
        scale: Math.min(2, Math.max(0.6, Number(stored.scale) || 1)),
        shape: CAMERA_SHAPES.includes(stored.shape) ? stored.shape : fallback.shape,
      };
    } catch (_) {
      return fallback;
    }
  }

  function writeCameraState(state) {
    try {
      window.localStorage.setItem(CAMERA_STATE_KEY, JSON.stringify(state));
    } catch (_) {
      /* storage unavailable: the preview still works for this session */
    }
  }

  // Precise detection instead of styling every <video> on the page: the source
  // must be a live camera track (screen shares report a displaySurface), and
  // the full-stage background video is excluded by geometry.
  function isCameraPreview(video) {
    const stream = video.srcObject;
    if (!stream || typeof stream.getVideoTracks !== "function") return false;
    const [track] = stream.getVideoTracks();
    if (!track || track.readyState !== "live") return false;
    const settings = typeof track.getSettings === "function" ? track.getSettings() : {};
    if (settings.displaySurface) return false;
    if (video.closest("#live2d")) return false;
    const rect = video.getBoundingClientRect();
    const coversStage = rect.width >= window.innerWidth * 0.6 && rect.height >= window.innerHeight * 0.6;
    return !coversStage;
  }

  function findCameraStream() {
    for (const video of document.querySelectorAll("video")) {
      try {
        if (isCameraPreview(video)) return video.srcObject;
      } catch (_) {
        /* a detached element can throw while the app re-renders */
      }
    }
    return null;
  }

  function applyCameraState(state) {
    if (!cameraPip) return;
    cameraPip.style.setProperty("--pet-pip-x", `${state.x}px`);
    cameraPip.style.setProperty("--pet-pip-y", `${state.y}px`);
    cameraPip.style.setProperty("--pet-pip-scale", String(state.scale));
    CAMERA_SHAPES.forEach((shape) => cameraPip.classList.toggle(`is-${shape}`, shape === state.shape));
    const shapeButton = cameraPip.querySelector('[data-action="pip-shape"]');
    if (shapeButton) shapeButton.textContent = CAMERA_SHAPE_LABELS[state.shape];
    writeCameraState(state);
  }

  function createCameraPip() {
    const pip = node("div");
    pip.id = "slai-pet-camera-pip";
    pip.hidden = true;
    pip.setAttribute("aria-label", "摄像头预览");

    const video = document.createElement("video");
    video.autoplay = true;
    video.playsInline = true;
    video.muted = true;
    video.className = "slai-pet-pip-video";
    pip.append(video);

    const veil = node("div", "slai-pet-pip-veil");
    pip.append(veil);

    const badge = node("div", "slai-pet-pip-badge");
    badge.append(node("i", "slai-pet-pip-dot"), node("span", "", "正在提供画面"));
    pip.append(badge);

    const controls = node("div", "slai-pet-pip-controls");
    const shape = node("button", "slai-pet-pip-button", "16:9");
    shape.type = "button";
    shape.dataset.action = "pip-shape";
    shape.title = "切换预览形状";
    const zoomOut = node("button", "slai-pet-pip-button", "−");
    zoomOut.type = "button";
    zoomOut.title = "缩小预览";
    const zoomIn = node("button", "slai-pet-pip-button", "＋");
    zoomIn.type = "button";
    zoomIn.title = "放大预览";
    const stop = node("button", "slai-pet-pip-button slai-pet-pip-stop", "停止画面");
    stop.type = "button";
    stop.title = "立即停止摄像头画面";
    controls.append(shape, zoomOut, zoomIn, stop);
    pip.append(controls);

    let state = readCameraState();

    shape.addEventListener("click", () => {
      const next = CAMERA_SHAPES[(CAMERA_SHAPES.indexOf(state.shape) + 1) % CAMERA_SHAPES.length];
      state = { ...state, shape: next };
      applyCameraState(state);
    });
    zoomOut.addEventListener("click", () => {
      state = { ...state, scale: Math.max(0.6, Number((state.scale - 0.15).toFixed(2))) };
      applyCameraState(state);
    });
    zoomIn.addEventListener("click", () => {
      state = { ...state, scale: Math.min(2, Number((state.scale + 0.15).toFixed(2))) };
      applyCameraState(state);
    });

    // Two-step stop: no modal dialog (they freeze the automation bridge) but
    // still no accidental kill of a live stream.
    let armed = false;
    let armedTimer = null;
    stop.addEventListener("click", () => {
      if (!armed) {
        armed = true;
        stop.textContent = "确认停止";
        stop.classList.add("is-armed");
        armedTimer = window.setTimeout(() => {
          armed = false;
          stop.textContent = "停止画面";
          stop.classList.remove("is-armed");
        }, 4000);
        return;
      }
      window.clearTimeout(armedTimer);
      armed = false;
      stop.textContent = "停止画面";
      stop.classList.remove("is-armed");
      stopCameraStream();
    });

    // Dragging moves our own container only; the app's own preview is never
    // touched, so React keeps owning its DOM.
    let dragging = null;
    badge.addEventListener("pointerdown", (event) => {
      dragging = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, originX: state.x, originY: state.y };
      badge.setPointerCapture(event.pointerId);
      pip.classList.add("is-dragging");
    });
    badge.addEventListener("pointermove", (event) => {
      if (!dragging || dragging.pointerId !== event.pointerId) return;
      const x = Math.max(8, Math.min(window.innerWidth - 80, dragging.originX + (event.clientX - dragging.startX)));
      const y = Math.max(8, Math.min(window.innerHeight - 80, dragging.originY + (event.clientY - dragging.startY)));
      state = { ...state, x, y };
      applyCameraState(state);
    });
    const endDrag = (event) => {
      if (!dragging || dragging.pointerId !== event.pointerId) return;
      dragging = null;
      pip.classList.remove("is-dragging");
    };
    badge.addEventListener("pointerup", endDrag);
    badge.addEventListener("pointercancel", endDrag);

    document.body.append(pip);
    cameraPip = pip;
    applyCameraState(state);
    return pip;
  }

  function stopCameraStream() {
    try {
      cameraStream?.getTracks().forEach((track) => track.stop());
    } catch (_) {
      /* the app may already have released the device */
    }
    detachCameraStream();
  }

  function detachCameraStream() {
    cameraStream = null;
    if (!cameraPip) return;
    const video = cameraPip.querySelector(".slai-pet-pip-video");
    if (video) video.srcObject = null;
    cameraPip.hidden = true;
  }

  function syncCameraPip() {
    const stream = findCameraStream();
    if (!stream) {
      if (cameraStream) detachCameraStream();
      return;
    }
    if (stream === cameraStream) return;
    cameraStream = stream;
    if (!cameraPip) createCameraPip();
    const video = cameraPip.querySelector(".slai-pet-pip-video");
    video.srcObject = stream;
    video.play?.().catch(() => {});
    cameraPip.hidden = false;
  }

  function watchCamera() {
    syncCameraPip();
    cameraScanTimer = window.setInterval(syncCameraPip, 2000);
    if (typeof MutationObserver === "function") {
      cameraObserver = new MutationObserver(() => syncCameraPip());
      cameraObserver.observe(document.body, { childList: true, subtree: true });
    }
  }

  // --- Living world: time of day drives the background ---------------------

  // The app renders its background as an <img> served from /bg/. Find it by
  // that data, not by a generated class name, and attach our own cross-fading
  // layer as a sibling instead of taking over React's element.
  function findBackgroundHost() {
    const appBackground = document.querySelector('img[src*="/bg/"]');
    if (appBackground && appBackground.parentElement) return appBackground.parentElement;
    const stage = document.getElementById("live2d");
    if (stage) return stage;
    return null;
  }

  function ensureWorldLayer() {
    if (worldLayer && worldLayer.isConnected) return worldLayer;
    const host = findBackgroundHost();
    const layer = node("div");
    layer.id = "slai-pet-world-bg";
    layer.setAttribute("aria-hidden", "true");
    layer.append(
      node("div", "slai-pet-world-layer is-front"),
      node("div", "slai-pet-world-layer"),
      node("div", "slai-pet-world-tint"),
    );
    if (host) {
      layer.classList.add("is-hosted");
      host.append(layer);
    } else {
      // No stage yet: sit behind everything at the page level.
      document.body.prepend(layer);
    }
    worldLayer = layer;
    return layer;
  }

  function applyWorldBackground(background) {
    if (!background) return;
    const key = `${background.url || ""}|${background.gradient}|${background.tint}`;
    if (key === currentBackgroundKey) return;
    currentBackgroundKey = key;

    const layer = ensureWorldLayer();
    const layers = [...layer.querySelectorAll(".slai-pet-world-layer")];
    const incoming = layers[worldLayerFlip ? 0 : 1];
    const outgoing = layers[worldLayerFlip ? 1 : 0];
    worldLayerFlip = !worldLayerFlip;

    incoming.style.backgroundImage = background.url
      ? `url("${background.url}")`
      : background.gradient;
    incoming.classList.add("is-front");
    outgoing.classList.remove("is-front");

    const tint = layer.querySelector(".slai-pet-world-tint");
    if (tint) tint.style.background = background.tint || "transparent";
  }

  function renderWorld(panel, payload) {
    const strip = panel.querySelector('[data-field="world"]');
    if (!strip || !payload || !payload.event) return;
    const { event, now } = payload;
    strip.querySelector('[data-field="world-phase"]').textContent = now.phase_label;
    strip.querySelector('[data-field="world-behavior"]').textContent = event.behavior_label;
    strip.querySelector('[data-field="world-note"]').textContent = event.note || "";
    strip.dataset.phase = now.phase;
    strip.dataset.reason = event.reason;

    const until = new Date(event.expected_end_at);
    const remain = strip.querySelector('[data-field="world-remaining"]');
    if (!Number.isNaN(until.getTime())) {
      const minutes = Math.max(0, Math.round((until.getTime() - Date.now()) / 60000));
      remain.textContent = minutes >= 60
        ? `约 ${Math.round(minutes / 60)} 小时后换下一件事`
        : `约 ${minutes} 分钟后换下一件事`;
    } else {
      remain.textContent = "";
    }

    applyWorldBackground(payload.background);

    // The offline summary is shown once per event, never replayed as a queue
    // of animations the user missed.
    if (payload.offline_summary && event.event_id !== currentWorldEventId) {
      setMessage(panel, payload.offline_summary);
    }
    currentWorldEventId = event.event_id;
  }

  async function loadWorld(panel) {
    try {
      const response = await fetch("/api/pet/world?user_id=default", { cache: "no-store" });
      if (!response.ok) return;
      renderWorld(panel, await response.json());
    } catch (_) {
      /* the world strip is decorative: never block the status card on it */
    }
  }

  function rememberReaction(eventId) {
    if (!eventId) return true;
    if (seenReactionIds.has(eventId)) return false;
    seenReactionIds.add(eventId);
    if (seenReactionIds.size > 200) {
      seenReactionIds.delete(seenReactionIds.values().next().value);
    }
    return true;
  }

  // One bubble surface, two sources: deterministic action reactions and the
  // pet's own filtered speech. Speech never overwrites a running reaction.
  function writeBubble(layer, text, variant) {
    const bubble = layer.querySelector('[data-field="reaction-bubble"]');
    const body = layer.querySelector('[data-field="bubble-text"]');
    const expand = layer.querySelector(".slai-pet-bubble-expand");
    body.textContent = text;
    bubble.classList.toggle("is-speech", variant === "speech");
    bubble.classList.remove("is-expanded");
    expand.textContent = "展开";
    expand.hidden = text.length <= 60;
    return bubble;
  }

  function revealBubble(panel, layer, canvas, duration, options) {
    const withPanelPulse = !options || options.panelPulse !== false;
    layer.classList.remove("is-visible");
    if (withPanelPulse) panel.classList.remove("is-reacting");
    void layer.offsetWidth;
    layer.classList.add("is-visible");
    if (withPanelPulse) panel.classList.add("is-reacting");
    window.clearTimeout(speechHideTimer);
    speechHideTimer = window.setTimeout(() => {
      layer.classList.remove("is-visible");
      panel.classList.remove("is-reacting");
      canvas?.classList.remove("slai-pet-live2d-reacting");
    }, duration);
  }

  function showSpeech(panel, layer, message) {
    const text = String(message.text || "").trim();
    if (!text) return;
    rememberSpeech(message);
    if (panel.classList.contains("is-reacting")) return;
    const canvas = positionReactionLayer(layer);
    writeBubble(layer, message.truncated ? `${text}…` : text, "speech");
    const duration = Math.min(
      SPEECH_MAX_MS,
      SPEECH_BASE_MS + text.length * SPEECH_PER_CHAR_MS,
    );
    revealBubble(panel, layer, canvas, duration, { panelPulse: false });
    positionReactionLayer(layer);
  }

  function playReaction(panel, layer, eventId, reaction, render) {
    if (!reaction || !rememberReaction(eventId)) return;
    const duration = Number(reaction.duration_ms) || 3200;
    const nativeMode = applyLive2dRender(renderPlanFor(reaction, render), duration);
    playReactionSound(reaction.sound);
    const canvas = positionReactionLayer(layer);
    writeBubble(layer, reaction.bubble || "好开心！", "reaction");
    layer.querySelectorAll(".slai-pet-fish-particle").forEach((item) => item.remove());
    const glyph = particleGlyphs[reaction.particle];
    if (glyph) {
      for (let index = 0; index < 7; index += 1) {
        // The class name is the existing styling/animation hook; only the
        // glyph changes per action.
        const particle = node("span", "slai-pet-fish-particle", glyph);
        particle.style.setProperty("--pet-particle-x", `${(Math.random() - 0.5) * 150}px`);
        particle.style.setProperty("--pet-particle-delay", `${index * 55}ms`);
        layer.append(particle);
      }
    }

    // The canvas highlight stays as the always-available degradation: it is
    // the only feedback left when the model has neither motion nor expression.
    canvas?.classList.add("slai-pet-live2d-reacting");
    revealBubble(panel, layer, canvas, duration);
    positionReactionLayer(layer);
    setMessage(panel, reaction.bubble || "小光做出了回应");
    window.dispatchEvent(new CustomEvent("slai-pet-reaction", {
      detail: { eventId, reaction, render: render || null, nativeMode },
    }));

  }

  async function loadState(panel) {
    const response = await fetch("/api/pet/state?user_id=default", { cache: "no-store" });
    if (!response.ok) throw new Error(`状态接口返回 ${response.status}`);
    const payload = await response.json();
    render(panel, payload);
    return payload;
  }

  function actionButtons(panel) {
    return [...panel.querySelectorAll("[data-action]")].filter(
      (button) => button.dataset.action !== "refresh" && button.dataset.action !== "sound",
    );
  }

  async function runPetAction(panel, reactionLayer, actionName) {
    const action = petActions[actionName];
    if (!action) return;
    const buttons = actionButtons(panel);
    buttons.forEach((button) => {
      button.disabled = true;
    });
    setMessage(panel, action.busy);
    try {
      const response = await fetch(action.path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "default",
          ...action.body,
          // A fresh id per click: retries of the same click stay idempotent
          // server side, but a new click is a new intent.
          request_id: `ui-${actionName}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        }),
      });
      if (!response.ok) throw new Error(`接口返回 ${response.status}`);
      const result = await response.json();
      if (currentProfile && result.state) renderState(panel, result.state);
      playReaction(panel, reactionLayer, result.event_id, result.reaction, result.render);
      setMessage(panel, result.message);
      loadWorld(panel);
    } catch (error) {
      setMessage(panel, `操作失败：${error.message}`, true);
    } finally {
      buttons.forEach((button) => {
        button.disabled = false;
      });
    }
  }

  function connectEventStream(panel, reactionLayer) {
    window.clearTimeout(reconnectTimer);
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/api/pet/events?user_id=default`;
    eventSocket = new WebSocket(url);

    eventSocket.addEventListener("open", () => {
      reconnectAttempt = 0;
    });
    eventSocket.addEventListener("message", (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch (_) {
        return;
      }
      if (payload.type === "pet_events_ready") {
        loadState(panel).catch((error) => setMessage(panel, `状态读取失败：${error.message}`, true));
      } else if (payload.type === "pet_state_changed" && payload.state) {
        renderState(panel, payload.state);
        setMessage(panel, "真实状态已同步");
        loadWorld(panel);
      } else if (payload.type === "pet_reaction") {
        playReaction(panel, reactionLayer, payload.event_id, payload.reaction, payload.render);
      } else if (payload.type === "pet_speech") {
        showSpeech(panel, reactionLayer, payload);
      }
    });
    eventSocket.addEventListener("close", () => {
      const delay = Math.min(10000, 1000 * (2 ** reconnectAttempt));
      reconnectAttempt += 1;
      reconnectTimer = window.setTimeout(() => connectEventStream(panel, reactionLayer), delay);
    });
    eventSocket.addEventListener("error", () => eventSocket.close());
  }

  window.addEventListener("DOMContentLoaded", () => {
    const panel = createPanel();
    const reactionLayer = createReactionLayer();
    drawerPanel = createDrawer();
    let drawerWasOpen = false;
    try {
      drawerWasOpen = window.localStorage.getItem("slai-pet-drawer-open") === "true";
    } catch (_) {
      drawerWasOpen = false;
    }
    if (drawerWasOpen) toggleDrawer(null, true);
    loadRecentSpeech();
    watchCamera();
    loadWorld(panel);
    // The world moves on its own: a slow tick is enough for phase changes.
    worldTimer = window.setInterval(() => loadWorld(panel), 60000);
    window.addEventListener("resize", () => {
      if (reactionLayer.classList.contains("is-visible")) positionReactionLayer(reactionLayer);
    });
    Object.keys(petActions).forEach((actionName) => {
      const button = panel.querySelector(`[data-action="${actionName}"]`);
      if (button) {
        button.addEventListener("click", () => runPetAction(panel, reactionLayer, actionName));
      }
    });
    panel.querySelector('[data-action="refresh"]').addEventListener("click", () => loadState(panel).catch((error) => setMessage(panel, `状态读取失败：${error.message}`, true)));
    loadState(panel).catch((error) => setMessage(panel, `状态读取失败：${error.message}`, true));
    connectEventStream(panel, reactionLayer);
    window.setInterval(() => loadState(panel).catch(() => {}), 60000);
  });

  window.addEventListener("beforeunload", () => {
    window.clearTimeout(reconnectTimer);
    window.clearTimeout(speechHideTimer);
    window.clearTimeout(expressionRestoreTimer);
    window.clearTimeout(sleepIdleTimer);
    bubbleAnchorObserver?.disconnect();
    cameraObserver?.disconnect();
    window.clearInterval(cameraScanTimer);
    window.clearInterval(worldTimer);
    eventSocket?.close();
  });
})();
