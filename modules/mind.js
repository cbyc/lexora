const MAX_QUESTION_LENGTH = 1000;

export function init(container, apiBase) {
  const messages = [];

  container.innerHTML = `
    <div class="chat-wrapper">
      <div id="chat-history" class="chat-history"></div>
      <div class="chat-input-area">
        <div class="flex gap-3">
          <div class="flex-1 relative">
            <textarea id="chat-input"
                      class="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
                      rows="3"
                      placeholder="Ask a question about your knowledge base..."
                      maxlength="${MAX_QUESTION_LENGTH}"></textarea>
            <span id="char-count" class="absolute bottom-2 right-3 text-xs text-gray-400"></span>
          </div>
          <button id="chat-send"
                  class="self-end px-5 py-3 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0">
            Send
          </button>
        </div>
        <p class="text-xs text-gray-400 mt-1">Press Ctrl+Enter to send</p>
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
      charCount.classList.toggle("text-red-500", len > MAX_QUESTION_LENGTH);
      charCount.classList.toggle("text-gray-400", len <= MAX_QUESTION_LENGTH);
    } else {
      charCount.textContent = "";
    }
    sendBtn.disabled = len === 0 || len > MAX_QUESTION_LENGTH;
  }

  function renderMessage(msg) {
    const div = document.createElement("div");
    const isUser = msg.role === "user";

    div.className = `chat-message ${isUser ? "chat-message-user" : "chat-message-assistant"}`;

    let html = `
      <div class="chat-role">${isUser ? "You" : "Lexora Mind"}</div>
      <div class="chat-text">${escapeHtml(msg.text)}</div>
    `;

    if (msg.sources && msg.sources.length > 0) {
      const sourceItems = msg.sources
        .map((src) => {
          if (src.startsWith("http://") || src.startsWith("https://")) {
            return `<li><a href="${escapeHtml(src)}" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:text-blue-800 hover:underline break-all">${escapeHtml(src)}</a></li>`;
          }
          return `<li class="text-gray-600 break-all">${escapeHtml(src)}</li>`;
        })
        .join("");
      html += `
        <div class="chat-sources">
          <span class="font-medium text-gray-500">Sources:</span>
          <ul class="mt-1 space-y-0.5">${sourceItems}</ul>
        </div>
      `;
    }

    if (msg.isError) {
      div.classList.add("chat-message-error");
    }

    div.innerHTML = html;
    history.appendChild(div);
    history.scrollTop = history.scrollHeight;
  }

  function addLoadingIndicator() {
    const div = document.createElement("div");
    div.id = "chat-loading";
    div.className = "chat-message chat-message-assistant";
    div.innerHTML = `
      <div class="chat-role">Lexora Mind</div>
      <div class="chat-text text-gray-400">Thinking...</div>
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
      const resp = await fetch(`${apiBase}/api/v1/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      removeLoadingIndicator();

      if (resp.ok) {
        const data = await resp.json();
        const assistantMsg = {
          role: "assistant",
          text: data.answer,
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
