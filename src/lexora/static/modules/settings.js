export async function init(container, _apiBase) {
  container.innerHTML = `
    <div class="settings-page">

      <section class="settings-section">
        <div class="settings-section-head">
          <h2 class="settings-section-title">API Credentials</h2>
          <p class="settings-section-desc">External service keys</p>
        </div>
        <div class="settings-section-body">
          <div class="settings-field">
            <div class="settings-label-row">
              <label class="settings-label" for="settings-api-key">Google API Key</label>
              <span id="settings-key-badge" class="settings-badge"></span>
            </div>
            <input id="settings-api-key" type="password" class="settings-input"
                   placeholder="Enter new key to update" autocomplete="off">
            <span class="settings-hint">Used for Gemini embeddings and knowledge base search</span>
          </div>
        </div>
      </section>

      <div class="settings-divider"></div>

      <section class="settings-section">
        <div class="settings-section-head">
          <h2 class="settings-section-title">Knowledge Base</h2>
          <p class="settings-section-desc">Document source directories</p>
        </div>
        <div class="settings-section-body">
          <div class="settings-field">
            <div class="settings-label-row">
              <label class="settings-label" for="settings-notes-dir">Notes Directory</label>
            </div>
            <div class="settings-input-row">
              <input id="settings-notes-dir" type="text" class="settings-input">
              <button class="settings-browse-btn" data-target="settings-notes-dir">Browse&hellip;</button>
            </div>
            <span class="settings-hint">Directory containing .txt note files</span>
          </div>

          <div class="settings-field">
            <div class="settings-label-row">
              <label class="settings-label" for="settings-bookmarks-dir">Firefox Profile Directory</label>
            </div>
            <div class="settings-input-row">
              <input id="settings-bookmarks-dir" type="text" class="settings-input"
                     placeholder="Leave blank to auto-detect">
              <button class="settings-browse-btn" data-target="settings-bookmarks-dir">Browse&hellip;</button>
            </div>
            <span class="settings-hint">Path to Firefox profile for bookmark sync</span>
          </div>

          <div class="settings-field">
            <span class="settings-hint">Re-index the knowledge base from the notes directory above and browser bookmarks.</span>
            <div style="margin-top:0.5rem">
              <button id="settings-reindex-btn" class="settings-reindex-btn">Reindex</button>
              <span id="settings-reindex-status" class="settings-reindex-status" style="display:none"></span>
            </div>
          </div>
        </div>
      </section>

      <div id="settings-banner" class="settings-banner" style="display:none"></div>
      <p id="settings-error" class="settings-error-msg" style="display:none"></p>

      <div class="settings-divider"></div>

      <div class="settings-actions">
        <button id="settings-save-btn" class="settings-save-btn">Save Settings</button>
      </div>

    </div>
  `;

  const apiKeyInput = container.querySelector("#settings-api-key");
  const notesDirInput = container.querySelector("#settings-notes-dir");
  const bookmarksDirInput = container.querySelector("#settings-bookmarks-dir");
  const keyBadge = container.querySelector("#settings-key-badge");
  const banner = container.querySelector("#settings-banner");
  const errorEl = container.querySelector("#settings-error");
  const saveBtn = container.querySelector("#settings-save-btn");
  const reindexBtn = container.querySelector("#settings-reindex-btn");
  const reindexStatus = container.querySelector("#settings-reindex-status");

  function setKeyBadge(isSet) {
    if (isSet) {
      keyBadge.textContent = "Set";
      keyBadge.className = "settings-badge settings-badge-set";
    } else {
      keyBadge.textContent = "Not configured";
      keyBadge.className = "settings-badge settings-badge-unset";
    }
  }

  // ── Load current settings ────────────────────────────────────────
  try {
    const resp = await fetch("/api/v1/settings");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    setKeyBadge(data.google_api_key_set);
    notesDirInput.value = data.notes_dir ?? "";
    bookmarksDirInput.value = data.bookmarks_profile_path ?? "";
  } catch (err) {
    errorEl.textContent = `Failed to load settings: ${err.message}`;
    errorEl.style.display = "";
  }

  // ── Browse buttons ───────────────────────────────────────────────
  container.querySelectorAll(".settings-browse-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        const resp = await fetch("/api/v1/settings/browse-directory", { method: "POST" });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (data.path) {
          const targetId = btn.dataset.target;
          container.querySelector(`#${targetId}`).value = data.path;
        }
      } catch (err) {
        errorEl.textContent = `Browse failed: ${err.message}`;
        errorEl.style.display = "";
      } finally {
        btn.disabled = false;
      }
    });
  });

  // ── Reindex ──────────────────────────────────────────────────────
  reindexBtn.addEventListener("click", async () => {
    reindexBtn.disabled = true;
    reindexBtn.textContent = "Reindexing\u2026";
    reindexStatus.style.display = "none";
    reindexStatus.className = "settings-reindex-status";

    try {
      const resp = await fetch("/api/v1/reindex", { method: "POST" });
      if (resp.status === 409) {
        reindexStatus.textContent = "Reindex is already running.";
        reindexStatus.className = "settings-reindex-status amber";
        reindexStatus.style.display = "";
      } else if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      } else {
        reindexStatus.textContent = "Reindex started \u2014 running in the background.";
        reindexStatus.className = "settings-reindex-status success";
        reindexStatus.style.display = "";
        setTimeout(() => { reindexStatus.style.display = "none"; }, 6000);
      }
    } catch (err) {
      errorEl.textContent = `Reindex failed: ${err.message}`;
      errorEl.style.display = "";
    } finally {
      reindexBtn.disabled = false;
      reindexBtn.textContent = "Reindex";
    }
  });

  // ── Save ─────────────────────────────────────────────────────────
  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    banner.style.display = "none";
    errorEl.style.display = "none";

    const body = {
      google_api_key: apiKeyInput.value,
      notes_dir: notesDirInput.value,
      bookmarks_profile_path: bookmarksDirInput.value,
    };

    try {
      const resp = await fetch("/api/v1/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      apiKeyInput.value = "";
      if (body.google_api_key) {
        setKeyBadge(true);
      }
      banner.textContent = "Settings saved. Restart the server for changes to take effect.";
      banner.style.display = "";
    } catch (err) {
      errorEl.textContent = `Failed to save settings: ${err.message}`;
      errorEl.style.display = "";
    } finally {
      saveBtn.disabled = false;
    }
  });
}
