const petId = "demo";
const stateLabels = {
  hunger: "饥饿",
  energy: "精力",
  health: "健康",
  mood: "心情",
  intimacy: "亲密度",
};

const shell = document.querySelector("#world-shell");
const stage = document.querySelector("#world-stage");
const connectionStatus = document.querySelector("#connection-status");
const personaName = document.querySelector("#persona-name");
const stateList = document.querySelector("#state-list");
const bubble = document.querySelector("#world-bubble");
const toast = document.querySelector("#action-toast");
const needsRail = document.querySelector("#needs-rail");
const liveAnnouncer = document.querySelector("#live-announcer");
const artifactResult = document.querySelector("#artifact-result");
const proactiveResult = document.querySelector("#proactive-result");
const worldFrame = document.querySelector("#live2d-world");

const stateChipLabels = {
  mood: "心情",
  energy: "精力",
  hunger: "饱腹",
  intimacy: "亲密",
};

const actionCopy = {
  play: "摸摸一下，开心能量 +1",
  feed: "给它准备一口热乎乎的饭",
  adventure: "一起出发，去房间外探险",
  chat: "我在听，你慢慢说",
};

const actionMotion = {
  play: { index: 0, expression: "exp_01" },
  feed: { index: 1, expression: "exp_02" },
  adventure: { index: 2, expression: "exp_05" },
  chat: { index: 3, expression: "exp_03" },
};

const staticDemo = window.location.hostname.endsWith("github.io")
  || new URLSearchParams(window.location.search).has("static");
const staticStateKey = "slai-pet-world-static-state-v1";
const staticPersonas = [{ persona_id: "sunny", display_name: "小太阳" }];
const staticInitialState = {
  pet_id: petId,
  hunger: 20,
  energy: 80,
  health: 100,
  mood: 75,
  intimacy: 10,
  experience: 0,
  level: 1,
  maturity: 0,
};

function clamp(value) {
  return Math.max(0, Math.min(100, value));
}

function readStaticState() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(staticStateKey) || "null");
    return { ...staticInitialState, ...(saved || {}) };
  } catch {
    return { ...staticInitialState };
  }
}

function writeStaticState(state) {
  try {
    window.localStorage.setItem(staticStateKey, JSON.stringify(state));
  } catch {
    // Private browsing can deny localStorage; the current tab still works.
  }
  return state;
}

function staticAction(action) {
  const state = readStaticState();
  const changes = {
    feed: [-25, 0, 0, 5, 1, 10, "吃饱啦，肚子暖暖的！"],
    play: [0, -5, 0, 10, 3, 10, "被你摸摸啦，尾巴都要摇起来了！"],
    bathe: [0, 0, 8, 3, 0, 8, "洗得香喷喷，心情变好了！"],
    rest: [0, 30, 0, 4, 0, 5, "休息完成，电量回来啦！"],
    study: [4, -12, 0, 2, 0, 25, "学到新东西啦，变聪明一点点！"],
    work: [8, -20, 0, 1, 1, 30, "工作完成，今天也有小小收获！"],
    adventure: [10, -25, 0, 8, 2, 35, "冒险回来啦，发现了闪闪发光的经验！"],
  };
  const [hunger, energy, health, mood, intimacy, reward, message] = changes[action] || changes.play;
  const next = {
    ...state,
    hunger: clamp(state.hunger + hunger),
    energy: clamp(state.energy + energy),
    health: clamp(state.health + health),
    mood: clamp(state.mood + mood),
    intimacy: clamp(state.intimacy + intimacy),
    experience: state.experience + reward,
  };
  next.level = Math.floor(next.experience / 100) + 1;
  next.maturity = clamp(next.level * 12.5);
  writeStaticState(next);
  return { action, message, state: next, experience_gained: reward };
}

function staticResponse(text) {
  const normalized = text.trim();
  const action = normalized.includes("喂") || normalized.includes("吃饭")
    ? "feed"
    : normalized.includes("摸摸") || normalized.includes("玩耍") || normalized.includes("陪我玩")
      ? "play"
      : normalized.includes("冒险") || normalized.includes("出去玩")
        ? "adventure"
        : null;
  if (action) return staticAction(action);
  const state = readStaticState();
  const message = normalized.includes("怎么样") || normalized.includes("状态") || normalized.includes("在干嘛")
    ? `我现在心情${Math.round(state.mood)}分，精力${Math.round(state.energy)}分，正在房间里等你。`
    : "我听见啦。这个公开 Demo 会把成长状态保存在你的浏览器里。";
  return { message, state, action: null };
}

function staticArtifact(kind, payload) {
  const title = payload.title || (kind === "letter" ? "今天的晚安信" : "和主人一起看星星");
  if (kind === "letter") {
    const content = `# ${title}\n\n写给${payload.recipient || "主人"}：\n\n${payload.content || "今天也要好好休息，明天我们继续一起发光。"}\n`;
    return `data:text/markdown;charset=utf-8,${encodeURIComponent(content)}`;
  }
  const drawing = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 320"><rect width="480" height="320" rx="28" fill="#111524"/><circle cx="360" cy="84" r="42" fill="#f0b36a" opacity=".92"/><path d="M126 210 92 112l86 40c28-18 72-18 100 0l86-40-34 98c18 22 23 46 16 68-12 36-54 54-118 54s-106-18-118-54c-7-22-2-46 16-68Z" fill="#f0b36a"/><circle cx="184" cy="214" r="11" fill="#111524"/><circle cx="272" cy="214" r="11" fill="#111524"/><path d="M192 250c20 16 52 16 72 0" fill="none" stroke="#111524" stroke-width="9" stroke-linecap="round"/></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(drawing)}`;
}

function staticApi(path, options = {}) {
  let body = {};
  try {
    body = options.body ? JSON.parse(options.body) : {};
  } catch {
    return Promise.reject(new Error("公开演示无法读取这次请求"));
  }
  if (path.startsWith("/state")) return Promise.resolve(readStaticState());
  if (path === "/personas") return Promise.resolve(staticPersonas);
  if (path === "/actions") return Promise.resolve(staticAction(body.action));
  if (path === "/respond") return Promise.resolve(staticResponse(body.text || ""));
  if (path.startsWith("/skills/")) {
    const kind = path.split("/").pop();
    return Promise.resolve({ path: staticArtifact(kind, body) });
  }
  if (path === "/observe") return Promise.resolve({ should_trigger: true, action: "wave", message: "我看到你回来啦，今天也一起发光吧！" });
  return Promise.reject(new Error("这个公开演示暂未开放该功能"));
}

function api(path, options = {}) {
  if (staticDemo) return staticApi(path, options);
  return fetch(`/api/pet${path}`, {
    headers: { "content-type": "application/json" },
    ...options,
  }).then(async (response) => {
    const data = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(data.detail)
        ? data.detail.map((item) => item.msg || "请求参数不正确").join("；")
        : data.detail;
      throw new Error(detail || "宠物服务暂时不可用");
    }
    return data;
  });
}

function setBusy(button, busy) {
  button.disabled = busy;
  button.classList.toggle("is-busy", busy);
  button.setAttribute("aria-busy", String(busy));
}

function setConnection(connected, text) {
  connectionStatus.textContent = text;
  connectionStatus.dataset.connected = String(connected);
  shell.dataset.connected = String(connected);
}

function levelFor(value) {
  return value < 30 ? "low" : value < 70 ? "medium" : "high";
}

function moodFor(state) {
  if (state.mood >= 70 && state.energy >= 45) return "happy";
  if (state.energy < 35 || state.health < 45) return "tired";
  return "calm";
}

function renderState(state) {
  const rows = Object.entries(stateLabels).map(([key, label]) => {
    const value = Math.round(state[key]);
    const level = levelFor(value);
    return `<div class="state-row state-${key}" data-state-level="${level}">
      <div class="state-label"><span>${label}</span><span class="state-value">${value}/100</span></div>
      <div class="progress" role="progressbar" aria-label="${label}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${value}"><span style="width:${Math.max(0, Math.min(100, state[key]))}%"></span></div>
    </div>`;
  }).join("");
  stateList.innerHTML = rows;

  needsRail.innerHTML = ["mood", "energy", "hunger", "intimacy"].map((key) => {
    const value = Math.round(state[key]);
    return `<span class="need-chip" data-state-level="${levelFor(value)}"><span>${stateChipLabels[key]}</span><strong>${value}</strong></span>`;
  }).join("");

  document.querySelector("#level-badge").textContent = `LV ${state.level}`;
  document.querySelector("#growth-copy").textContent = `${state.experience} XP`;
  document.querySelector("#growth-bar").style.width = `${state.experience % 100}%`;
  stage.dataset.mood = moodFor(state);
}

function showBubble(message) {
  bubble.textContent = message;
  bubble.classList.remove("is-hidden");
}

function showToast(message, action) {
  stage.dataset.action = action;
  toast.textContent = message;
  toast.classList.remove("is-visible");
  void toast.offsetWidth;
  toast.classList.add("is-visible");
  window.setTimeout(() => {
    toast.classList.remove("is-visible");
    delete stage.dataset.action;
  }, 1900);
}

function showResult(message, action = "talk") {
  showBubble(message);
  showToast(message, action);
  liveAnnouncer.textContent = message;
}

function triggerWorldMotion(action) {
  const adapter = worldFrame.contentWindow?.getLAppAdapter?.();
  const motion = actionMotion[action];
  if (!adapter || !motion) {
    stage.dataset.motionReady = "false";
    return false;
  }
  try {
    const groups = adapter.getMotionGroups();
    const group = groups.find((name) => name !== "Idle") ?? groups[0];
    adapter.startMotion(group, motion.index, 3);
    if (motion.expression) adapter.setExpression(motion.expression);
    stage.dataset.motionReady = "true";
    stage.dataset.motionAction = action;
    return true;
  } catch (error) {
    console.warn("Live2D 动作暂时不可用", error);
    stage.dataset.motionReady = "false";
    return false;
  }
}

function concealUpstreamChrome() {
  const innerDocument = worldFrame.contentDocument;
  if (!innerDocument) return;
  const notificationRegion = innerDocument.querySelector('[data-part="group"][aria-label*="Notifications"]');
  if (notificationRegion) notificationRegion.style.display = "none";

  const chatCopy = [...innerDocument.querySelectorAll("*")].find(
    (element) => element.textContent?.trim() === "新对话已开始",
  );
  let candidate = chatCopy;
  while (candidate && candidate !== innerDocument.body) {
    const style = innerDocument.defaultView.getComputedStyle(candidate);
    const rect = candidate.getBoundingClientRect();
    if (["absolute", "fixed"].includes(style.position) && rect.width > 180 && rect.height > 35) {
      candidate.style.display = "none";
      break;
    }
    candidate = candidate.parentElement;
  }
}

function scheduleUpstreamChromeCleanup() {
  [120, 600, 1400, 2600].forEach((delay) => window.setTimeout(concealUpstreamChrome, delay));
  const innerDocument = worldFrame.contentDocument;
  if (!innerDocument?.body || innerDocument.__slaipetObserver) return;
  const observer = new innerDocument.defaultView.MutationObserver(concealUpstreamChrome);
  observer.observe(innerDocument.body, { childList: true, characterData: true, subtree: true });
  innerDocument.__slaipetObserver = observer;
}

function toggleDrawer(open) {
  shell.dataset.drawerOpen = String(open);
  const backdrop = document.querySelector("#drawer-backdrop");
  const drawer = document.querySelector("#control-drawer");
  const buttons = [document.querySelector("#drawer-button"), document.querySelector("#more-button")];
  backdrop.hidden = !open;
  drawer.setAttribute("aria-hidden", String(!open));
  buttons.forEach((button) => button.setAttribute("aria-expanded", String(open)));
  if (open) document.querySelector("#drawer-close").focus();
}

async function refreshState() {
  try {
    renderState(await api(`/state?pet_id=${petId}`));
    setConnection(true, "在线");
  } catch (error) {
    setConnection(false, "离线模式");
    showBubble(`我还在这里，但服务暂时没连上：${error.message}`);
  }
}

async function runAction(action, button) {
  setBusy(button, true);
  triggerWorldMotion(action);
  showToast(actionCopy[action] || "它有回应了", action);
  try {
    const result = await api("/actions", {
      method: "POST",
      body: JSON.stringify({ pet_id: petId, action }),
    });
    renderState(result.state);
    showResult(result.message, action);
  } catch (error) {
    showResult(error.message, "error");
  } finally {
    setBusy(button, false);
  }
}

async function respond(text) {
  triggerWorldMotion("chat");
  showToast(actionCopy.chat, "chat");
  try {
    const result = await api("/respond", {
      method: "POST",
      body: JSON.stringify({ pet_id: petId, text }),
    });
    renderState(result.state);
    showResult(result.message, result.action?.action || "talk");
  } catch (error) {
    showResult(`我听见啦，但现在还不能回应：${error.message}`, "error");
  }
}

function focusChat() {
  const input = document.querySelector("#chat-input");
  input.focus();
  input.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

document.querySelector("#chat-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.querySelector("#chat-input");
  const text = input.value.trim();
  if (!text) return focusChat();
  input.value = "";
  respond(text);
});

document.querySelector("#chat-focus").addEventListener("click", focusChat);
document.querySelector("#wake-button").addEventListener("click", () => respond("你回来啦，我现在怎么样？"));

document.querySelectorAll("[data-action]").forEach((button) => {
  button.addEventListener("click", () => runAction(button.dataset.action, button));
});

document.querySelectorAll("[data-skill]").forEach((button) => {
  button.addEventListener("click", async () => {
    setBusy(button, true);
    const kind = button.dataset.skill;
    try {
      const result = await api(`/skills/${kind}`, {
        method: "POST",
        body: JSON.stringify({
          pet_id: petId,
          title: kind === "letter" ? "今天的晚安信" : "和主人一起看星星",
          recipient: "主人",
          content: kind === "letter" ? "今天也要好好休息，明天我们继续一起发光。" : "和主人一起看星星",
        }),
      });
      const link = document.createElement("a");
      link.href = result.path;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = `打开${kind === "letter" ? "信件" : "画作"}`;
      artifactResult.replaceChildren(document.createTextNode("已生成："), link);
      showResult(kind === "letter" ? "我写了一封信，放在抽屉里啦。" : "我画了一颗和你一起看的星星。", "create");
    } catch (error) {
      artifactResult.textContent = error.message;
    } finally {
      setBusy(button, false);
    }
  });
});

document.querySelectorAll("[data-event]").forEach((button) => {
  button.addEventListener("click", async () => {
    setBusy(button, true);
    try {
      const result = await api("/observe", {
        method: "POST",
        body: JSON.stringify({ event_type: button.dataset.event, observed_at: Date.now() / 1000 }),
      });
      proactiveResult.textContent = result.should_trigger
        ? `${result.message}（动作：${result.action}）`
        : "冷却中：宠物暂时不重复打扰你。";
      if (result.should_trigger) showResult(result.message, "presence");
    } catch (error) {
      proactiveResult.textContent = error.message;
    } finally {
      setBusy(button, false);
    }
  });
});

document.querySelector("#drawer-button").addEventListener("click", () => toggleDrawer(true));
document.querySelector("#more-button").addEventListener("click", () => toggleDrawer(true));
document.querySelector("#drawer-close").addEventListener("click", () => toggleDrawer(false));
document.querySelector("#drawer-backdrop").addEventListener("click", () => toggleDrawer(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") toggleDrawer(false);
});

let worldLoaded = false;
worldFrame.addEventListener("load", () => {
  worldLoaded = true;
  stage.dataset.worldLoaded = "true";
  scheduleUpstreamChromeCleanup();
  window.setTimeout(() => {
    stage.dataset.worldReady = "true";
  }, 2200);
});
window.setTimeout(() => {
  if (!worldLoaded) {
    stage.dataset.fallback = "true";
    stage.dataset.worldReady = "true";
    document.querySelector("#stage-fallback strong").textContent = "原始宠物世界暂时没有加载";
    document.querySelector("#stage-fallback span").textContent = "状态操作仍然可以继续使用";
  }
}, 6500);

api("/personas").then((personas) => {
  const sunny = personas.find((persona) => persona.persona_id === "sunny") || personas[0];
  if (sunny) personaName.textContent = sunny.display_name;
}).catch(() => {});

refreshState();
window.setInterval(refreshState, 15000);
