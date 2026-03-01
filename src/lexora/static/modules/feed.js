const RANGES = [
  { label: "Today", value: "today" },
  { label: "Last week", value: "last_week" },
  { label: "Last month", value: "last_month" },
  { label: "Last 3 months", value: "last_3_months" },
  { label: "Last 6 months", value: "last_6_months" },
  { label: "Last year", value: "last_year" },
  { label: "All time", value: "" },
];

export function init(container, apiBase) {
  let allPosts = [];

  container.innerHTML = `
    <div class="feed-controls">
      <div class="feed-control-group">
        <label for="range-select" class="feed-control-label">Range</label>
        <select id="range-select" class="feed-select">
          ${RANGES.map(
            (r) =>
              `<option value="${r.value}" ${r.value === "last_month" ? "selected" : ""}>${r.label}</option>`
          ).join("")}
        </select>
      </div>
      <div class="feed-control-group">
        <label for="feed-select" class="feed-control-label">Feed</label>
        <select id="feed-select" class="feed-select">
          <option value="">All Feeds</option>
        </select>
      </div>
      <button id="add-feed-btn" class="feed-add-btn">+ Add Feed</button>
    </div>
    <div id="feed-add-panel" class="feed-add-panel">
      <form id="feed-add-form" class="feed-add-form" novalidate>
        <div class="feed-add-form-row">
          <div class="feed-add-form-field">
            <label for="feed-name-input" class="feed-add-form-label">Name</label>
            <input id="feed-name-input" type="text" class="feed-add-form-input"
              placeholder="e.g. Hacker News" autocomplete="off" spellcheck="false">
          </div>
          <div class="feed-add-form-field">
            <label for="feed-url-input" class="feed-add-form-label">URL</label>
            <input id="feed-url-input" type="url" class="feed-add-form-input"
              placeholder="https://example.com/feed.xml" autocomplete="off" spellcheck="false">
          </div>
        </div>
        <div class="feed-add-form-actions">
          <span id="feed-add-feedback" class="feed-add-feedback"></span>
          <button type="button" id="feed-cancel-btn" class="feed-add-cancel-btn">Cancel</button>
          <button type="submit" id="feed-submit-btn" class="feed-add-submit-btn">Add Feed</button>
        </div>
      </form>
    </div>
    <div id="feed-warnings"></div>
    <div id="post-list"></div>
  `;

  const rangeSelect   = container.querySelector("#range-select");
  const feedSelect    = container.querySelector("#feed-select");
  const postList      = container.querySelector("#post-list");
  const warnings      = container.querySelector("#feed-warnings");
  const addBtn        = container.querySelector("#add-feed-btn");
  const addPanel      = container.querySelector("#feed-add-panel");
  const addForm       = container.querySelector("#feed-add-form");
  const addNameInput  = container.querySelector("#feed-name-input");
  const addUrlInput   = container.querySelector("#feed-url-input");
  const addSubmitBtn  = container.querySelector("#feed-submit-btn");
  const addCancelBtn  = container.querySelector("#feed-cancel-btn");
  const addFeedback   = container.querySelector("#feed-add-feedback");

  function updateFeedDropdown(posts) {
    const current = feedSelect.value;
    const feedNames = [...new Set(posts.map((p) => p.feed_name))].sort();

    feedSelect.innerHTML =
      '<option value="">All Feeds</option>' +
      feedNames
        .map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`)
        .join("");

    if (feedNames.includes(current)) {
      feedSelect.value = current;
    } else {
      feedSelect.value = "";
    }
  }

  function applyFeedFilter() {
    const selectedFeed = feedSelect.value;
    const filtered = selectedFeed
      ? allPosts.filter((p) => p.feed_name === selectedFeed)
      : allPosts;
    renderPosts(filtered, postList);
  }

  async function fetchPosts() {
    const range = rangeSelect.value;
    const url = range
      ? `${apiBase}/api/v1/rss?range=${range}`
      : `${apiBase}/api/v1/rss`;

    postList.innerHTML = '<p class="loading-text">Fetching posts\u2026</p>';
    warnings.innerHTML = "";

    try {
      const resp = await fetch(url);
      const feedErrors = resp.headers.get("X-Feed-Errors");
      allPosts = await resp.json();

      if (feedErrors === "all-feeds-failed") {
        warnings.innerHTML = `
          <details class="feed-warning">
            <summary>Some feeds failed to load</summary>
            <p style="margin-top:0.375rem;font-size:0.8125rem">All configured feeds failed to respond. Check your feed URLs and network connection.</p>
          </details>
        `;
      }

      updateFeedDropdown(allPosts);
      applyFeedFilter();
    } catch (err) {
      postList.innerHTML = `<p class="error-text">Failed to fetch posts: ${err.message}</p>`;
    }
  }

  function openAddPanel() {
    addPanel.classList.add("open");
    addBtn.classList.add("is-open");
    addBtn.textContent = "− Close";
    addNameInput.focus();
  }

  function closeAddPanel() {
    addPanel.classList.remove("open");
    addBtn.classList.remove("is-open");
    addBtn.textContent = "+ Add Feed";
    addForm.reset();
    addFeedback.textContent = "";
    addFeedback.className = "feed-add-feedback";
  }

  addBtn.addEventListener("click", () => {
    addPanel.classList.contains("open") ? closeAddPanel() : openAddPanel();
  });

  addCancelBtn.addEventListener("click", closeAddPanel);

  addForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = addNameInput.value.trim();
    const url = addUrlInput.value.trim();

    if (!name || !url) {
      addFeedback.textContent = "Name and URL are required.";
      addFeedback.className = "feed-add-feedback error";
      return;
    }

    addSubmitBtn.disabled = true;
    addFeedback.textContent = "Adding\u2026";
    addFeedback.className = "feed-add-feedback";

    try {
      const resp = await fetch(`${apiBase}/api/v1/rss`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, url }),
      });

      if (resp.ok) {
        addFeedback.textContent = `\u201c${escapeHtml(name)}\u201d added successfully.`;
        addFeedback.className = "feed-add-feedback success";
        setTimeout(() => {
          closeAddPanel();
          fetchPosts();
        }, 1400);
      } else {
        const body = await resp.json().catch(() => ({}));
        addFeedback.textContent = body.detail || `Error ${resp.status}`;
        addFeedback.className = "feed-add-feedback error";
      }
    } catch (err) {
      addFeedback.textContent = `Network error: ${err.message}`;
      addFeedback.className = "feed-add-feedback error";
    } finally {
      addSubmitBtn.disabled = false;
    }
  });

  rangeSelect.addEventListener("change", fetchPosts);
  feedSelect.addEventListener("change", applyFeedFilter);
  fetchPosts();
}

function renderPosts(posts, container) {
  if (posts.length === 0) {
    container.innerHTML = `
      <div class="feed-empty">
        <p class="feed-empty-title">No posts in this range.</p>
        <p class="feed-empty-body">Try a wider date range, or add a feed using the <strong>+ Add Feed</strong> button above.</p>
      </div>
    `;
    return;
  }

  const rows = posts
    .map(
      (post) => `
    <article class="feed-item">
      <span class="feed-item-source">${escapeHtml(post.feed_name)}</span>
      <a href="${escapeHtml(post.url)}"
         target="_blank"
         rel="noopener noreferrer"
         class="feed-item-title"
         title="${escapeHtml(post.title)}">${escapeHtml(post.title)}</a>
      <time class="feed-item-date" title="${post.published_at}">${relativeDate(post.published_at)}</time>
    </article>
  `
    )
    .join("");

  container.innerHTML = `<div class="feed-list">${rows}</div>`;
}

function relativeDate(isoString) {
  if (!isoString || isoString === "0001-01-01T00:00:00Z") return "\u2014";
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffDay > 30) return `${Math.floor(diffDay / 30)}mo`;
  if (diffDay > 0) return `${diffDay}d`;
  if (diffHr > 0) return `${diffHr}h`;
  if (diffMin > 0) return `${diffMin}m`;
  return "now";
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
