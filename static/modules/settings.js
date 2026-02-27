export async function init(container, _apiBase) {
  container.innerHTML = `
    <div class="settings-form">
      <div class="settings-section">
        <div class="settings-field">
          <label class="feed-control-label" for="settings-api-key">Google API Key</label>
          <input id="settings-api-key" type="password" class="settings-input" placeholder="Enter new key to update" autocomplete="off">
          <span id="settings-key-hint" class="settings-hint"></span>
        </div>
        <div class="settings-field">
          <label class="feed-control-label" for="settings-notes-dir">Notes Directory</label>
          <input id="settings-notes-dir" type="text" class="settings-input">
        </div>
        <div class="settings-field">
          <label class="feed-control-label" for="settings-bookmarks-dir">Firefox Profile Directory</label>
          <input id="settings-bookmarks-dir" type="text" class="settings-input" placeholder="Leave blank to auto-detect">
        </div>
      </div>
      <div id="settings-banner" style="display:none"></div>
      <p id="settings-error" class="error-text" style="display:none"></p>
      <button id="settings-save-btn" class="settings-save-btn">Save Settings</button>
    </div>
  `;

  const apiKeyInput = container.querySelector("#settings-api-key");
  const notesDirInput = container.querySelector("#settings-notes-dir");
  const bookmarksDirInput = container.querySelector("#settings-bookmarks-dir");
  const keyHint = container.querySelector("#settings-key-hint");
  const banner = container.querySelector("#settings-banner");
  const errorEl = container.querySelector("#settings-error");
  const saveBtn = container.querySelector("#settings-save-btn");

  try {
    const resp = await fetch("/api/v1/settings");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    if (data.google_api_key_set) {
      keyHint.textContent = "Currently set";
      keyHint.className = "settings-hint settings-hint-set";
    } else {
      keyHint.textContent = "Not configured";
      keyHint.className = "settings-hint settings-hint-unset";
    }
    notesDirInput.value = data.notes_dir ?? "";
    bookmarksDirInput.value = data.bookmarks_profile_path ?? "";
  } catch (err) {
    errorEl.textContent = `Failed to load settings: ${err.message}`;
    errorEl.style.display = "";
  }

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
        keyHint.textContent = "Currently set";
        keyHint.className = "settings-hint settings-hint-set";
      }
      banner.className = "feed-warning";
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
