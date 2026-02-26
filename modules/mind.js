const MAX_QUESTION_LENGTH = 1000;

export function init(container, apiBase) {
  const messages = [];

  container.innerHTML = `
    <div class="chat-wrapper">
      <div id="chat-history" class="chat-history"></div>
      <div class="chat-input-area">
        <div class="chat-input-row">
          <div class="chat-textarea-wrap">
            <textarea id="chat-input"
                      class="chat-textarea"
                      rows="3"
                      placeholder="Ask your knowledge base\u2026"
                      maxlength="${MAX_QUESTION_LENGTH}"></textarea>
            <span id="char-count" class="chat-char-count"></span>
          </div>
          <button id="chat-send" class="chat-send-btn" disabled>Send</button>
        </div>
        <p class="chat-hint">\u2318\u21B5 &nbsp;to send</p>
      </div>
    </div>
  `;

  const history = container.querySelector("#chat-history");
  const input = container.querySelector("#chat-input");
  const sendBtn = container.querySelector("#chat-send");
  const charCount = container.querySelector("#char-count");

  function updateCharCount() {
    const len = input.value.length;
    if (len > MAX_QUESTION_LENGTH * 0.8) {
      charCount.textContent = `${len}/${MAX_QUESTION_LENGTH}`;
      charCount.classList.toggle("warn", len > MAX_QUESTION_LENGTH);
    } else {
      charCount.textContent = "";
      charCount.classList.remove("warn");
    }
    sendBtn.disabled = len === 0 || len > MAX_QUESTION_LENGTH;
  }

  function renderMessage(msg) {
    const isUser = msg.role === "user";
    const div = document.createElement("div");
    div.className = `chat-msg ${isUser ? "chat-msg-user" : "chat-msg-assistant"}${msg.isError ? " chat-msg-error" : ""}`;

    if (isUser) {
      div.innerHTML = `
        <div class="chat-bubble">
          <div class="chat-msg-text">${escapeHtml(msg.text)}</div>
        </div>
      `;
    } else {
      let sourcesHtml = "";
      if (msg.sources && msg.sources.length > 0) {
        const items = msg.sources
          .map((src) => {
            if (src.startsWith("http://") || src.startsWith("https://")) {
              return `<li><a href="${escapeHtml(src)}" target="_blank" rel="noopener noreferrer">${escapeHtml(src)}</a></li>`;
            }
            return `<li><span class="source-text">${escapeHtml(src)}</span></li>`;
          })
          .join("");
        sourcesHtml = `
          <div class="chat-sources">
            <div class="chat-sources-label">Sources</div>
            <ul class="chat-sources-list">${items}</ul>
          </div>
        `;
      }

      div.innerHTML = `
        <div class="chat-bubble">
          <div class="chat-msg-label">Lexora Mind</div>
          <div class="chat-msg-text">${escapeHtml(msg.text)}</div>
          ${sourcesHtml}
        </div>
      `;
    }

    history.appendChild(div);
    history.scrollTop = history.scrollHeight;
  }

  function addLoadingIndicator() {
    const div = document.createElement("div");
    div.id = "chat-loading";
    div.className = "chat-msg chat-msg-assistant";
    div.innerHTML = `
      <div class="chat-bubble">
        <div class="chat-msg-label">Lexora Mind</div>
        <div class="chat-loading-dots">
          <div class="chat-loading-dot"></div>
          <div class="chat-loading-dot"></div>
          <div class="chat-loading-dot"></div>
        </div>
      </div>
    `;
    history.appendChild(div);
    history.scrollTop = history.scrollHeight;
  }

  function removeLoadingIndicator() {
    const loading = history.querySelector("#chat-loading");
    if (loading) loading.remove();
  }

  async function sendMessage() {
    const question = input.value.trim();
    if (!question || question.length > MAX_QUESTION_LENGTH) return;

    const userMsg = { role: "user", text: question };
    messages.push(userMsg);
    renderMessage(userMsg);

    input.value = "";
    updateCharCount();
    sendBtn.disabled = true;
    addLoadingIndicator();

    try {
      const resp = await fetch(`${apiBase}/api/v1/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      removeLoadingIndicator();

      if (resp.ok) {
        const data = await resp.json();
        const assistantMsg = {
          role: "assistant",
          text: data.text,
          sources: data.sources,
        };
        messages.push(assistantMsg);
        renderMessage(assistantMsg);
      } else {
        let detail = "An unexpected error occurred.";
        try {
          const errData = await resp.json();
          detail = errData.detail || detail;
        } catch {}
        const errorMsg = {
          role: "assistant",
          text: detail,
          isError: true,
        };
        messages.push(errorMsg);
        renderMessage(errorMsg);
      }
    } catch {
      removeLoadingIndicator();
      const errorMsg = {
        role: "assistant",
        text: "Failed to reach the knowledge base. Check that the service is running.",
        isError: true,
      };
      messages.push(errorMsg);
      renderMessage(errorMsg);
    }

    sendBtn.disabled = false;
    input.focus();
  }

  sendBtn.addEventListener("click", sendMessage);

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      sendMessage();
    }
  });

  input.addEventListener("input", updateCharCount);
  updateCharCount();
  input.focus();
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
