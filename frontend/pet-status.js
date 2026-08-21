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
  const activityNames = { resting: "休息中", eating: "吃东西", tired: "有点累" };
  const locationNames = { pet_home: "宠物家园" };

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
    const toggle = node("button", "slai-pet-icon-button", "⌃");
    toggle.type = "button";
    toggle.title = "收起宠物状态";
    toggle.addEventListener("click", () => {
      const collapsed = panel.classList.toggle("is-collapsed");
      toggle.textContent = collapsed ? "⌄" : "⌃";
      toggle.title = collapsed ? "展开宠物状态" : "收起宠物状态";
      localStorage.setItem("slai-pet-panel-collapsed", String(collapsed));
    });
    head.append(title, toggle);

    const body = node("div", "slai-pet-body");
    const meta = node("div", "slai-pet-meta");
    meta.append(node("i", "slai-pet-dot"));
    const activity = node("b", "", "同步中");
    activity.dataset.field = "activity";
    const location = node("span", "", "宠物家园");
    location.dataset.field = "location";
    meta.append(activity, node("span", "", "·"), location);
    body.append(meta);

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

  function setMessage(panel, text, isError = false) {
    const message = panel.querySelector('[data-field="message"]');
    message.textContent = text;
    message.dataset.error = String(isError);
  }

  function render(panel, payload) {
    const { profile, state } = payload;
    panel.querySelector('[data-field="name"]').textContent = profile.name || "小光";
    panel.querySelector('[data-field="persona"]').textContent = `${profile.persona} · ${profile.voice || "默认音色"}`;
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
    const tags = panel.querySelector('[data-field="capabilities"]');
    tags.replaceChildren(...profile.capabilities.map((item) => node("span", "slai-pet-tag", item)));
    setMessage(panel, `“${profile.catchphrase}” · 状态已持久化`);
  }

  async function loadState(panel) {
    const response = await fetch("/api/pet/state?user_id=default", { cache: "no-store" });
    if (!response.ok) throw new Error(`状态接口返回 ${response.status}`);
    const payload = await response.json();
    render(panel, payload);
  }

  async function feedPet(panel) {
    const button = panel.querySelector('[data-action="feed"]');
    button.disabled = true;
    setMessage(panel, "小光正在吃小鱼干…");
    try {
      const response = await fetch("/api/pet/feed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "default",
          food: "小鱼干",
          request_id: `ui-feed-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        }),
      });
      if (!response.ok) throw new Error(`喂食接口返回 ${response.status}`);
      const result = await response.json();
      await loadState(panel);
      setMessage(panel, result.message);
    } catch (error) {
      setMessage(panel, `喂食失败：${error.message}`, true);
    } finally {
      button.disabled = false;
    }
  }

  window.addEventListener("DOMContentLoaded", () => {
    const panel = createPanel();
    panel.querySelector('[data-action="feed"]').addEventListener("click", () => feedPet(panel));
    panel.querySelector('[data-action="refresh"]').addEventListener("click", () => loadState(panel).catch((error) => setMessage(panel, `状态读取失败：${error.message}`, true)));
    loadState(panel).catch((error) => setMessage(panel, `状态读取失败：${error.message}`, true));
    window.setInterval(() => loadState(panel).catch(() => {}), 60000);
  });
})();
