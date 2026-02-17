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
    <div class="flex items-center gap-6 mb-4 flex-wrap">
      <div class="flex items-center gap-2">
        <label for="range-select" class="text-sm font-medium text-gray-600">Date range:</label>
        <select id="range-select"
                class="border border-gray-300 rounded px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
          ${RANGES.map(
            (r) =>
              `<option value="${r.value}" ${r.value === "last_month" ? "selected" : ""}>${r.label}</option>`
          ).join("")}
        </select>
      </div>
      <div class="flex items-center gap-2">
        <label for="feed-select" class="text-sm font-medium text-gray-600">Feed:</label>
        <select id="feed-select"
                class="border border-gray-300 rounded px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All Feeds</option>
        </select>
      </div>
    </div>
    <div id="feed-warnings"></div>
    <div id="post-list"></div>
  `;

  const rangeSelect = container.querySelector("#range-select");
  const feedSelect = container.querySelector("#feed-select");
  const postList = container.querySelector("#post-list");
  const warnings = container.querySelector("#feed-warnings");

  function updateFeedDropdown(posts) {
    const current = feedSelect.value;
    const feedNames = [...new Set(posts.map((p) => p.feed_name))].sort();

    // Rebuild options, preserving selection if still valid
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
      ? `${apiBase}/rss?range=${range}`
      : `${apiBase}/rss`;

    postList.innerHTML = '<p class="text-gray-400 text-sm">Loading posts...</p>';
    warnings.innerHTML = "";

    try {
      const resp = await fetch(url);
      const feedErrors = resp.headers.get("X-Feed-Errors");
      allPosts = await resp.json();

      if (feedErrors === "all-feeds-failed") {
        warnings.innerHTML = `
          <details class="warning-banner">
            <summary>Some feeds failed to load</summary>
            <p class="mt-1">All configured feeds failed to respond. Check your feed URLs and network connection.</p>
          </details>
        `;
      }

      updateFeedDropdown(allPosts);
      applyFeedFilter();
    } catch (err) {
      postList.innerHTML = `<p class="text-red-500 text-sm">Failed to fetch posts: ${err.message}</p>`;
    }
  }

  rangeSelect.addEventListener("change", fetchPosts);
  feedSelect.addEventListener("change", applyFeedFilter);
  fetchPosts();
}

function renderPosts(posts, container) {
  if (posts.length === 0) {
    container.innerHTML = `
      <div class="text-center py-12 text-gray-500">
        <p class="text-lg mb-2">No posts found for this time range.</p>
        <p class="text-sm">Try selecting a wider date range, or add feeds via the API:</p>
        <code class="block mt-2 text-xs bg-gray-100 p-2 rounded max-w-lg mx-auto text-left">curl -X PUT http://localhost:9001/rss \\
  -H "Content-Type: application/json" \\
  -d '{"name": "Example", "url": "https://example.com/rss"}'</code>
      </div>
    `;
    return;
  }

  const rows = posts
    .map(
      (post) => `
    <div class="post-row flex items-center gap-4 px-4 py-2.5 border-b border-gray-100">
      <span class="feed-name text-xs font-medium text-gray-400 uppercase tracking-wide shrink-0">${escapeHtml(post.feed_name)}</span>
      <a href="${escapeHtml(post.url)}"
         target="_blank"
         rel="noopener noreferrer"
         class="post-title flex-1 text-sm text-blue-700 hover:text-blue-900 hover:underline"
         title="${escapeHtml(post.title)}">${escapeHtml(post.title)}</a>
      <span class="text-xs text-gray-400 shrink-0 whitespace-nowrap"
            title="${post.published_at}">${relativeDate(post.published_at)}</span>
    </div>
  `
    )
    .join("");

  container.innerHTML = `<div class="border border-gray-200 rounded-lg overflow-hidden">${rows}</div>`;
}

function relativeDate(isoString) {
  if (!isoString || isoString === "0001-01-01T00:00:00Z") return "unknown";
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffDay > 30) return `${Math.floor(diffDay / 30)}mo ago`;
  if (diffDay > 0) return `${diffDay}d ago`;
  if (diffHr > 0) return `${diffHr}h ago`;
  if (diffMin > 0) return `${diffMin}m ago`;
  return "just now";
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
