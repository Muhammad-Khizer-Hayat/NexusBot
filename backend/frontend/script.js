const API = "https://nexusbot-assistant.up.railway.app/api";
// const API  = "/api";   // same address as the page: works locally and on any host
const GCID = "638940044835-r945jm44cf3mhmdmi36f6uroc2nqmnse.apps.googleusercontent.com";   // ← paste your FULL Google Client ID here (ends in .apps.googleusercontent.com)

const BOT_AVATAR_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="22" height="22">
  <polygon points="16,2 28,9 28,23 16,30 4,23 4,9" fill="#6c63ff"/>
  <line x1="10" y1="11" x2="10" y2="21" stroke="white" stroke-width="2.8" stroke-linecap="round"/>
  <line x1="10" y1="11" x2="22" y2="21" stroke="white" stroke-width="2.8" stroke-linecap="round"/>
  <line x1="22" y1="14" x2="22" y2="21" stroke="white" stroke-width="2.8" stroke-linecap="round"/>
</svg>`;

// ── State ──────────────────────────────────────────────────────
let token       = localStorage.getItem("nb_token") || "";
let currentUser = JSON.parse(localStorage.getItem("nb_user") || "null");
let sessions    = [];
let currentSid  = null;
let messages    = [];
let isTyping    = false;
let ttsEnabled  = true;
let recognition = null;
let isListening = false;


// ══════════════════════════════════════════════════════════════
// AUTH
// ══════════════════════════════════════════════════════════════
function authH() {
    const h = { "Content-Type": "application/json" };
    if (token) h["Authorization"] = `Bearer ${token}`;
    return h;
}
function showAuthError(msg) {
    const el = document.getElementById("auth-error");
    el.textContent = msg; el.style.display = "block";
    document.getElementById("auth-success").style.display = "none";
}
function clearAuthMsg() {
    document.getElementById("auth-error").style.display   = "none";
    document.getElementById("auth-success").style.display = "none";
}
function switchTab(tab) {
    document.getElementById("login-form").style.display    = tab === "login"    ? "block" : "none";
    document.getElementById("register-form").style.display = tab === "register" ? "block" : "none";
    document.getElementById("tab-login").classList.toggle("active",    tab === "login");
    document.getElementById("tab-register").classList.toggle("active", tab === "register");
    clearAuthMsg();
}
async function doLogin() {
    const btn = document.getElementById("login-btn");
    const username = document.getElementById("login-id").value.trim();
    const password = document.getElementById("login-password").value;
    if (!username || !password) return showAuthError("Please fill all fields");
    btn.textContent = "Signing in…"; btn.disabled = true;
    try {
        const r = await fetch(`${API}/auth/login`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({username, password})});
        const d = await r.json();
        if (d.token) { saveAuth(d.token, d.user); initApp(); }
        else showAuthError(d.error || d.detail || "Login failed");
    } catch { showAuthError("Cannot connect to server. Make sure the backend is running."); }
    btn.textContent = "Sign In"; btn.disabled = false;
}
async function doRegister() {
    const btn = document.getElementById("register-btn");
    const username = document.getElementById("reg-username").value.trim();
    const email    = document.getElementById("reg-email").value.trim();
    const password = document.getElementById("reg-password").value;
    if (!username || !password) return showAuthError("Username and password required");
    btn.textContent = "Creating…"; btn.disabled = true;
    try {
        const r = await fetch(`${API}/auth/register`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({username, email, password})});
        const d = await r.json();
        if (d.token) { saveAuth(d.token, d.user); initApp(); }
        else showAuthError(d.error || d.detail || "Registration failed");
    } catch { showAuthError("Cannot connect to server."); }
    btn.textContent = "Create Account"; btn.disabled = false;
}
function googleSignIn() {
    if (!GCID || GCID === "YOUR_GOOGLE_CLIENT_ID_HERE") {
        showAuthError("Google Sign-In not configured. Paste your Client ID in script.js and .env");
        return;
    }
    if (typeof google === "undefined" || !google.accounts) {
        showAuthError("Google library not loaded. Check your internet connection and refresh.");
        return;
    }
    let container = document.getElementById("g-btn-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "g-btn-container";
        container.style.cssText = "position:fixed;top:-9999px;left:-9999px;";
        document.body.appendChild(container);
    }
    container.innerHTML = "";
    google.accounts.id.initialize({
        client_id: GCID,
        callback: async (response) => {
            try {
                const r = await fetch(`${API}/auth/google`, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({id_token: response.credential})
                });
                const d = await r.json();
                if (d.token) { saveAuth(d.token, d.user); initApp(); }
                else showAuthError(d.error || d.detail || "Google login failed");
            } catch(e) {
                showAuthError("Could not reach server: " + (e && e.message ? e.message : e));
            }
        },
        ux_mode: "popup",
    });
    google.accounts.id.renderButton(container, {
        theme: "outline", size: "large", type: "standard",
        text: "signin_with", shape: "rectangular", width: 280,
    });
    setTimeout(() => {
        const btn = container.querySelector("div[role=button]") || container.querySelector("iframe");
        if (btn) btn.click();
        else showAuthError("Could not open Google Sign-In. Please allow popups and try again.");
    }, 300);
}
function guestMode() {
    token = ""; currentUser = {id:0, username:"Guest", email:"", avatar:""};
    localStorage.removeItem("nb_token");
    localStorage.setItem("nb_user", JSON.stringify(currentUser));
    initApp();
}
function saveAuth(t, user) {
    token = t; currentUser = user;
    localStorage.setItem("nb_token", t);
    localStorage.setItem("nb_user",  JSON.stringify(user));
}
function logout() {
    token = ""; currentUser = null; sessions = []; currentSid = null; messages = [];
    localStorage.removeItem("nb_token"); localStorage.removeItem("nb_user");
    document.getElementById("app").style.display         = "none";
    document.getElementById("auth-screen").style.display = "flex";
    document.getElementById("login-id").value = "";
    document.getElementById("login-password").value = "";
    clearAuthMsg();
}

// ══════════════════════════════════════════════════════════════
// INIT
// ══════════════════════════════════════════════════════════════
window.onload = () => {
    if (token || currentUser) { initApp(); }
    else { document.getElementById("auth-screen").style.display = "flex"; }
    document.addEventListener("click", (e) => {
        const popup = document.getElementById("plus-popup");
        const btn   = document.getElementById("plus-btn");
        if (popup && !popup.contains(e.target) && !btn.contains(e.target)) {
            popup.style.display = "none";
            btn.classList.remove("active");
        }
    });
};

async function initApp() {
    document.getElementById("auth-screen").style.display = "none";
    document.getElementById("app").style.display         = "flex";
    const u = currentUser || {username:"Guest", avatar:""};
    document.getElementById("user-name").textContent = u.username;
    const av = document.getElementById("user-avatar");
    if (u.avatar) { av.innerHTML = `<img src="${u.avatar}" alt="${u.username}"/>`; }
    else { av.textContent = u.username.charAt(0).toUpperCase(); }
    updateActionBtn();
    initVoice();
    updateDatetime();
    setInterval(updateDatetime, 60000);
    loadDocumentList();
    await loadSessions();
}

function updateDatetime() {
    const el = document.getElementById("datetime-pill");
    if (el) el.textContent = new Date().toLocaleString("en-US",
        {weekday:"short", month:"short", day:"numeric", hour:"2-digit", minute:"2-digit"});
}

// ══════════════════════════════════════════════════════════════
// PLUS POPUP MENU
// ══════════════════════════════════════════════════════════════
function togglePlusPopup() {
    const popup = document.getElementById("plus-popup");
    const btn   = document.getElementById("plus-btn");
    const isOpen = popup.style.display === "block";
    popup.style.display = isOpen ? "none" : "block";
    btn.classList.toggle("active", !isOpen);
}
function triggerFileUpload(type) {
    document.getElementById("plus-popup").style.display = "none";
    document.getElementById("plus-btn").classList.remove("active");
    if (type === "file")  document.getElementById("input-file-any").click();
    if (type === "image") document.getElementById("input-file-image").click();
    if (type === "pdf")   document.getElementById("input-file-pdf").click();
}
function handleAnyFile(file) {
    if (!file) return;
    const ext = file.name.split(".").pop().toLowerCase();
    const imageExts = ["png","jpg","jpeg","gif","bmp","webp","tiff"];
    const docExts   = ["pdf","txt","md"];
    if (imageExts.includes(ext)) {
        handleImageUpload(file);
    } else if (docExts.includes(ext)) {
        uploadFile(file);
    } else {
        appendBubble("⚠️ Unsupported file type. Use images (PNG/JPG) or documents (PDF/TXT/MD).", "bot", true);
    }
    document.getElementById("input-file-any").value = "";
}

// ══════════════════════════════════════════════════════════════
// IMAGE UPLOAD & OCR
// ══════════════════════════════════════════════════════════════
async function handleImageUpload(file) {
    if (!file) return;
    const ext     = file.name.split(".").pop().toLowerCase();
    const allowed = ["png","jpg","jpeg","gif","bmp","webp","tiff"];
    if (!allowed.includes(ext)) {
        appendBubble("⚠️ Only image files supported: PNG, JPG, JPEG, GIF, BMP, WEBP.", "bot", true);
        return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
        const box = document.getElementById("messages");
        document.getElementById("welcome")?.remove();
        const row = document.createElement("div"); row.className = "msg-row user";
        const av  = document.createElement("div"); av.className = "avatar user-av"; av.textContent = "U";
        const bub = document.createElement("div"); bub.className = "bubble user-bubble";
        bub.innerHTML = `<div style="font-size:11px;margin-bottom:6px;opacity:.85">📷 ${file.name}</div><img src="${e.target.result}" class="img-preview" alt="uploaded image"/>`;
        row.appendChild(av); row.appendChild(bub); box.appendChild(row);
        box.scrollTop = box.scrollHeight;
    };
    reader.readAsDataURL(file);
    const typingId = showTyping();
    const fd = new FormData(); fd.append("image", file);
    try {
        const res  = await fetch(`${API}/upload-image`, { method: "POST", body: fd });
        const data = await res.json();
        removeTyping(typingId);
        if (data.success) {
            const reply = `## OCR Result — ${data.filename}\n\n${data.text}`;
            messages.push({role:"assistant", content: reply});
            appendBubble(reply, "bot", true);
            speak(data.text);
        } else {
            appendBubble(`⚠️ ${data.error || "OCR failed"}`, "bot", true);
        }
    } catch {
        removeTyping(typingId);
        appendBubble("⚠️ Image upload failed. Make sure the backend is running.", "bot", true);
    }
    document.getElementById("input-file-image").value = "";
}

// ══════════════════════════════════════════════════════════════
// SESSIONS
// ══════════════════════════════════════════════════════════════
async function loadSessions() {
    try {
        const r = await fetch(`${API}/sessions`, {headers: authH()});
        const d = await r.json();
        sessions = d.sessions || [];
    } catch { sessions = []; }
    renderHistory();
    if (sessions.length > 0) { await loadSession(sessions[0].id); }
    else { newChat(); }
}
async function loadSession(sid) {
    currentSid = sid;
    try {
        const r = await fetch(`${API}/sessions/${sid}`, {headers: authH()});
        const d = await r.json();
        messages = d.messages || [];
    } catch { messages = []; }
    const box = document.getElementById("messages");
    box.innerHTML = "";
    if (messages.length === 0) { showWelcome(); }
    else { messages.forEach(m => appendBubble(m.content, m.role==="user"?"user":"bot", false, m.time||new Date().toLocaleTimeString("en-US",{hour:"2-digit",minute:"2-digit"}))); box.scrollTop = box.scrollHeight; }
    renderHistory();
}
function newChat() {
    stopSpeaking();
    if (currentSid) {
        fetch(`${API}/new-chat`, {method:"POST", headers:authH(), body:JSON.stringify({session_id:currentSid})}).catch(()=>{});
    }
    currentSid = `${currentUser?.id||0}_${Date.now()}`;
    messages   = [];
    sessions.unshift({id: currentSid, title: "New Chat", created_at: new Date().toISOString()});
    renderHistory();
    showWelcome();
}
async function deleteChat(sid, e) {
    e.stopPropagation();
    await fetch(`${API}/sessions/${sid}`, {method:"DELETE", headers:authH()}).catch(()=>{});
    sessions = sessions.filter(s => s.id !== sid);
    if (sid === currentSid) {
        if (sessions.length > 0) { await loadSession(sessions[0].id); }
        else { currentSid = null; newChat(); }
    } else { renderHistory(); }
}
function renderHistory() {
    const c     = document.getElementById("chat-history");
    const label = c.querySelector(".history-label");
    c.innerHTML = ""; c.appendChild(label);
    sessions.forEach(s => {
        const div = document.createElement("div");
        div.className = "history-item" + (s.id === currentSid ? " active" : "");
        div.innerHTML = `<span class="history-title">${s.title || "New Chat"}</span><button class="history-del" title="Delete">✕</button>`;
        div.querySelector(".history-del").onclick = (e) => deleteChat(s.id, e);
        div.onclick = () => loadSession(s.id);
        c.appendChild(div);
    });
}

// ══════════════════════════════════════════════════════════════
// WELCOME
// ══════════════════════════════════════════════════════════════
function showWelcome() {
    document.getElementById("messages").innerHTML = `
    <div class="welcome-screen" id="welcome">
      <div class="welcome-logo">N</div>
      <h1 class="welcome-title">How can I help you today?</h1>
      <p class="welcome-sub">Powered by LangGraph + ReAct + RAG + Web Search</p>
      <div class="suggestion-grid">
        <div class="suggestion" onclick="suggest(this)"><div class="sug-icon">🌤️</div><div class="sug-text">What is the weather in Lahore today?</div></div>
        <div class="suggestion" onclick="suggest(this)"><div class="sug-icon">🔍</div><div class="sug-text">Top software companies in Pakistan</div></div>
        <div class="suggestion" onclick="suggest(this)"><div class="sug-icon">💻</div><div class="sug-text">Write a Python web scraper using BeautifulSoup</div></div>
        <div class="suggestion" onclick="suggest(this)"><div class="sug-icon">🧮</div><div class="sug-text">What is 18% of 75000?</div></div>
        <div class="suggestion" onclick="suggest(this)"><div class="sug-icon">🎨</div><div class="sug-text">Generate image of sunset over mountains</div></div>
        <div class="suggestion" onclick="suggest(this)"><div class="sug-icon">🎤</div><div class="sug-text">Tap the waveform button and talk to me!</div></div>
      </div>
    </div>`;
}
function suggest(el) { document.getElementById("user-input").value = el.querySelector(".sug-text").textContent; sendMessage(); }

// ══════════════════════════════════════════════════════════════
// SEND MESSAGE
// ══════════════════════════════════════════════════════════════
async function sendMessage() {
    if (isTyping) return;
    const input = document.getElementById("user-input");
    const btn   = document.getElementById("send-btn");
    const text  = input.value.trim();
    if (!text) return;
    stopSpeaking();
    document.getElementById("welcome")?.remove();
    const _sendNow  = new Date();
    const sendTime  = _sendNow.toLocaleTimeString("en-US", {hour:"2-digit", minute:"2-digit"});
    const sendFull  = _sendNow.toLocaleString("en-US", {weekday:"short", year:"numeric", month:"short", day:"numeric", hour:"2-digit", minute:"2-digit", second:"2-digit"});
    messages.push({role:"user", content:text, time:sendTime, timeFull:sendFull});
    appendBubble(text, "user", true, sendTime, sendFull);
    input.value = ""; input.style.height = "auto";
    updateActionBtn();
    isTyping = true; btn.disabled = true;
    const tid = showTyping();
    try {
        const safeMessages = messages.map(m => {
            if (!m.content) return m;
            if (m.content.includes("[IMAGE]") || m.content.includes("data:image") || m.content.includes("[Image was generated]")) {
                return {...m, content: "[Image was generated]"};
            }
            if (m.content.length > 4000) {
                return {...m, content: m.content.slice(0, 4000)};
            }
            return m;
        });

        const res = await fetch(`${API}/chat`, {
            method: "POST", headers: authH(),
            body: JSON.stringify({messages: safeMessages, session_id: currentSid, stream: true})
        });

        removeTyping(tid);

        const reader  = res.body.getReader();
        const decoder = new TextDecoder();
        let   fullReply = "";
        let   meta      = {};
        let   bubbleEl  = null;
        let   sseBuf    = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            sseBuf += decoder.decode(value, { stream: true });
            const lines = sseBuf.split("\n");
            sseBuf = lines.pop();                        // keep the unfinished last line for the next chunk
            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                try {
                    const ev = JSON.parse(line.slice(6));
                    if (ev.type === "meta") {
                        meta = ev;
                        bubbleEl = appendStreamingBubble();
                    }
                    if (ev.type === "token") {
                        fullReply += ev.text;
                        const isImageChunk = fullReply.includes("[IMAGE]");
                        if (bubbleEl && !isImageChunk) updateStreamingBubble(bubbleEl, fullReply);
                        else if (bubbleEl && isImageChunk) {
                            bubbleEl.innerHTML = '<div style="padding:16px;text-align:center;color:#aaa;">🎨 Rendering image...</div>';
                        }
                    }
                    if (ev.type === "done") {
                        if (bubbleEl) finaliseStreamingBubble(bubbleEl, fullReply);
                    }
                } catch {}
            }
        }

        const reply = fullReply || "Sorry, no response.";
        const safeReply = (reply.includes("[IMAGE]") || reply.includes("data:image"))
            ? "[Image was generated]"
            : reply;
        messages.push({role:"assistant", content: safeReply});

        if (!reply.includes("[IMAGE]")) speak(reply);

        const s = sessions.find(s => s.id === currentSid);
        if (s && s.title === "New Chat") { s.title = text.length>45 ? text.slice(0,45)+"…" : text; renderHistory(); }
    } catch {
        removeTyping(tid);
        appendBubble("⚠️ Could not reach the server. Make sure the backend is running.", "bot", true);
    } finally { isTyping = false; btn.disabled = false; input.focus(); }
}

// ── Streaming bubble helpers ───────────────────────────────────
function appendStreamingBubble() {
    const box = document.getElementById("messages");
    const row = document.createElement("div"); row.className = "msg-row bot";
    const av  = document.createElement("div"); av.className  = "avatar bot-av"; av.innerHTML = BOT_AVATAR_SVG;
    const bub = document.createElement("div"); bub.className = "bubble bot-bubble streaming-bubble";
    bub.innerHTML = '<span class="stream-cursor">▋</span>';
    row.appendChild(av); row.appendChild(bub); box.appendChild(row);
    box.scrollTop = box.scrollHeight;
    return bub;
}
function updateStreamingBubble(bub, text) {
    if (text.includes('[IMAGE]') || text.includes('[WEATHER_CARD]')) {
        bub.innerHTML = '<span class="stream-cursor">▋</span>';
    } else if (text.includes('```mermaid') || /^\s*(flowchart|sequenceDiagram|classDiagram)/m.test(text)) {
        bub.innerHTML = '<div style="padding:12px;color:var(--tx3);font-size:13px;">📊 Building diagram...</div><span class="stream-cursor">▋</span>';
    } else {
        bub.innerHTML = renderMarkdown(text) + '<span class="stream-cursor">▋</span>';
    }
    const box = document.getElementById("messages");
    box.scrollTop = box.scrollHeight;
}
function finaliseStreamingBubble(bub, text) {
    const wd = parseWeatherCard(text);
    if (wd) {
        bub.innerHTML = buildWeatherCard(wd);
    } else if (parseImageCard(text)) {
        bub.innerHTML = buildImageCard(parseImageCard(text));
    } else {
        bub.innerHTML = renderMarkdown(text);
        bub.querySelectorAll("pre code").forEach(b => hljs.highlightElement(b));
        if (bub.querySelector(".mermaid-container")) {
            setTimeout(() => renderMermaidBlocks(bub), 200);
        }
    }
    bub.classList.remove("streaming-bubble");
    const box = document.getElementById("messages");
    box.scrollTop = box.scrollHeight;
}

// ══════════════════════════════════════════════════════════════
// BUBBLES & MARKDOWN
// ══════════════════════════════════════════════════════════════
function appendBubble(text, role, scroll=true, msgTime=null, msgTimeFull=null) {
    const box = document.getElementById("messages");
    const row = document.createElement("div"); row.className = `msg-row ${role}`;
    const av  = document.createElement("div"); av.className = `avatar ${role==="bot"?"bot-av":"user-av"}`; if(role==="bot"){av.innerHTML=BOT_AVATAR_SVG;}else{av.textContent="U";}
    const bub = document.createElement("div"); bub.className = `bubble ${role==="bot"?"bot-bubble":"user-bubble"}`;
    if (role === "bot") {
        const wd = parseWeatherCard(text);
        if (wd) {
            bub.innerHTML = buildWeatherCard(wd);
        } else if (parseImageCard(text)) {
            bub.innerHTML = buildImageCard(parseImageCard(text));
        } else {
            bub.innerHTML = renderMarkdown(text);
            bub.querySelectorAll("pre code").forEach(b => hljs.highlightElement(b));
            if (bub.querySelector(".mermaid-container")) {
                setTimeout(() => renderMermaidBlocks(bub), 200);
            }
        }
        bub.appendChild(buildFeedbackBar(text));
    } else {
        const msgWrap = document.createElement("div");
        msgWrap.className = "user-msg-wrap";

        const msgText = document.createElement("div");
        msgText.className = "bubble user-bubble";
        msgText.textContent = text;
        msgText.dataset.userText = text;
        msgWrap.appendChild(msgText);

        const _now    = new Date();
        const timeStr = msgTime     || _now.toLocaleTimeString("en-US", {hour:"2-digit", minute:"2-digit"});
        const timeFull = msgTimeFull || _now.toLocaleString("en-US", {weekday:"short", year:"numeric", month:"short", day:"numeric", hour:"2-digit", minute:"2-digit", second:"2-digit"});

        const actionBar = document.createElement("div");
        actionBar.className = "user-action-bar";
        actionBar.innerHTML = `
            <span class="msg-time" title="${timeFull}">${timeStr}</span>
            <button class="ua-btn" title="Edit message">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
                Edit
            </button>
            <button class="ua-btn" title="Copy message" onclick="navigator.clipboard.writeText(this.closest('.user-msg-wrap').querySelector('.user-bubble').textContent).then(()=>{this.textContent='Copied!';setTimeout(()=>{this.innerHTML='<svg width=\'12\' height=\'12\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'currentColor\' stroke-width=\'2\'><rect x=\'9\' y=\'9\' width=\'13\' height=\'13\' rx=\'2\'/><path d=\'M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1\'/></svg> Copy\'},1500)})">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2"/>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
                Copy
            </button>`;

        const row_ref = row;
        const editBtn = actionBar.querySelector('button[title="Edit message"]');
        editBtn.onclick = () => {
            const userRows = document.querySelectorAll('.msg-row.user');
            const idx = Array.from(userRows).indexOf(row_ref);
            editMessage(idx);
        };

        msgWrap.appendChild(actionBar);
        bub.appendChild(msgWrap);
        bub.className = "user-bubble-outer";
    }
    row.appendChild(av); row.appendChild(bub); box.appendChild(row);
    if (scroll) box.scrollTop = box.scrollHeight;
}

function parseImageCard(text) {
    const m = text.match(/\[IMAGE\]([\s\S]*?)\[\/IMAGE\]/);
    return m ? m[1].trim() : null;
}

function buildImageCard(imageUrl) {
    const cardId = "imgcard_" + Math.random().toString(36).slice(2,8);
    const modal = document.createElement("div");
    modal.id = cardId + "_modal";
    modal.style.cssText = "display:none;position:fixed;inset:0;background:rgba(0,0,0,0.9);z-index:9999;align-items:center;justify-content:center;";
    modal.innerHTML = `
        <div style="background:#1a1a1a;border-radius:20px;padding:24px;max-width:600px;width:92%;position:relative;" onclick="event.stopPropagation()">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                <span style="color:#fff;font-size:15px;font-weight:600;">🎨 AI Generated Image</span>
                <button onclick="document.getElementById('${cardId}_modal').style.display='none'"
                    style="background:none;border:none;color:#aaa;font-size:22px;cursor:pointer;line-height:1;">✕</button>
            </div>
            <div style="position:relative;">
                <img src="${imageUrl}" id="${cardId}_modalimg" style="width:100%;border-radius:12px;display:block;"/>
                <button onclick="editImage_${cardId}()"
                    style="position:absolute;bottom:10px;left:10px;background:rgba(0,0,0,0.7);
                    color:#fff;border:none;border-radius:8px;padding:6px 14px;
                    font-size:13px;font-weight:600;cursor:pointer;backdrop-filter:blur(4px);">
                    ✏️ Edit
                </button>
                <button onclick="shareImage_${cardId}()"
                    style="position:absolute;bottom:10px;right:10px;background:rgba(0,0,0,0.7);
                    color:#fff;border:none;border-radius:50%;width:34px;height:34px;
                    cursor:pointer;display:flex;align-items:center;justify-content:center;">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
                        <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
                        <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
                    </svg>
                </button>
            </div>
            <div style="display:flex;justify-content:center;gap:24px;margin-top:20px;padding-top:16px;border-top:1px solid #333;">
                <div style="display:flex;flex-direction:column;align-items:center;gap:6px;">
                    <button id="${cardId}_copybtn" onclick="
                        navigator.clipboard.writeText('${imageUrl}').then(()=>{
                            document.getElementById('${cardId}_copybtn').style.background='#22c55e';
                            setTimeout(()=>document.getElementById('${cardId}_copybtn').style.background='#000',2000);
                        })"
                        style="width:52px;height:52px;border-radius:50%;background:#000;border:none;
                        cursor:pointer;display:flex;align-items:center;justify-content:center;
                        color:#fff;transition:background 0.3s;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
                            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
                        </svg>
                    </button>
                    <span style="font-size:11px;color:#aaa;">Copy link</span>
                </div>
                <div style="display:flex;flex-direction:column;align-items:center;gap:6px;">
                    <button onclick="downloadGeneratedImage('${imageUrl}', '${cardId}')"
                        style="width:52px;height:52px;border-radius:50%;background:#000;border:none;
                        cursor:pointer;display:flex;align-items:center;justify-content:center;color:#fff;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                    </button>
                    <span style="font-size:11px;color:#aaa;">Download</span>
                </div>
            </div>
        </div>`;
    modal.onclick = () => modal.style.display = "none";
    document.body.appendChild(modal);
    window[`editImage_${cardId}`] = function() {
        modal.style.display = "none";
        const lastUser = messages.slice().reverse().find(m => m.role === "user");
        if (lastUser) {
            document.getElementById("user-input").value = lastUser.content;
            document.getElementById("user-input").focus();
            updateActionBtn();
        }
    };
    window[`shareImage_${cardId}`] = function() {
        if (navigator.share) {
            navigator.share({ title: "AI Generated Image", url: imageUrl });
        } else {
            navigator.clipboard.writeText(imageUrl).then(() => alert("Link copied!"));
        }
    };
    return `
    <div class="image-card" style="max-width:512px;">
        <div style="position:relative;cursor:pointer;" onclick="document.getElementById('${cardId}_modal').style.display='flex'">
            <img src="${imageUrl}"
                id="${cardId}_thumb"
                style="width:100%;border-radius:16px;display:block;opacity:0;transition:opacity 0.4s;"
                onload="this.style.opacity='1'"
                onerror="handleImgError(this, '${imageUrl}')"/>
        </div>
        <div style="display:flex;justify-content:flex-end;margin-top:6px;">
            <button title="Download"
                onclick="downloadGeneratedImage('${imageUrl}', '${cardId}')"
                style="background:var(--surface2,#2a2a2a);border:none;border-radius:50%;
                width:34px;height:34px;cursor:pointer;display:flex;align-items:center;
                justify-content:center;color:var(--text,#fff);">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
            </button>
        </div>
    </div>`;
}

function handleImgError(img, originalUrl) {
    const retries = parseInt(img.dataset.retries || 0);
    if (retries < 3) {
        img.dataset.retries = retries + 1;
        setTimeout(() => {
            const sep = originalUrl.includes("?") ? "&" : "?";
            img.src = originalUrl + sep + "_retry=" + Date.now();
        }, 2000 * (retries + 1));
        img.parentElement.innerHTML = `
            <div style="padding:20px;text-align:center;color:#aaa;border-radius:12px;background:#1a1a1a;">
                <div style="font-size:24px;margin-bottom:8px;">🎨</div>
                <div>Generating image... please wait</div>
                <div style="font-size:12px;margin-top:6px;opacity:0.6;">Attempt ${retries + 1}/3</div>
            </div>`;
        setTimeout(() => {
            const newImg = document.createElement("img");
            newImg.src = originalUrl + (originalUrl.includes("?") ? "&" : "?") + "_r=" + Date.now();
            newImg.style.cssText = "width:100%;border-radius:16px;display:block;opacity:0;transition:opacity 0.4s;";
            newImg.dataset.retries = retries + 1;
            newImg.onload = () => { newImg.style.opacity = "1"; };
            newImg.onerror = () => handleImgError(newImg, originalUrl);
            img.parentElement.replaceWith((() => { const d = document.createElement("div"); d.style.cssText="position:relative;cursor:pointer;"; d.appendChild(newImg); return d; })());
        }, 2000 * (retries + 1) + 100);
    } else {
        img.parentElement.innerHTML = `
            <div style="padding:20px;text-align:center;border-radius:12px;background:#1a1a1a;">
                <div style="font-size:32px;margin-bottom:8px;">🖼️</div>
                <div style="color:#ccc;margin-bottom:12px;">Image ready — click to view</div>
                <a href="${originalUrl}" target="_blank" 
                   style="background:#7c6ef7;color:#fff;padding:8px 20px;border-radius:8px;
                   text-decoration:none;font-size:14px;font-weight:600;">
                   Open Image ↗
                </a>
            </div>`;
    }
}

async function downloadGeneratedImage(imageUrl, cardId) {
    try {
        const response = await fetch(imageUrl);
        const blob     = await response.blob();
        const ext      = blob.type.includes("png") ? "png" : "jpg";
        const url      = URL.createObjectURL(blob);
        const a        = document.createElement("a");
        a.href         = url;
        a.download     = `nexusbot_image_${Date.now()}.${ext}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch {
        window.open(imageUrl, "_blank");
    }
}

// ── Feedback bar ───────────────────────────────────────────────
function buildFeedbackBar(text) {
    const bar = document.createElement("div"); bar.className = "feedback-bar";
    const like = document.createElement("button");
    like.className = "fb-btn"; like.title = "Good response";
    like.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/><path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg> Like`;
    like.onclick = () => { like.classList.toggle("active-like"); dislike.classList.remove("active-dislike"); };
    const dislike = document.createElement("button");
    dislike.className = "fb-btn"; dislike.title = "Bad response";
    dislike.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/><path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg> Dislike`;
    dislike.onclick = () => { dislike.classList.toggle("active-dislike"); like.classList.remove("active-like"); };
    const regen = document.createElement("button");
    regen.className = "fb-btn"; regen.title = "Regenerate";
    regen.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> Regenerate`;
    regen.onclick = () => {
        const lastUser = messages.slice().reverse().find(m => m.role === "user");
        if (lastUser) { document.getElementById("user-input").value = lastUser.content; sendMessage(); }
    };
    const copy = document.createElement("button");
    copy.className = "fb-btn fb-copy"; copy.title = "Copy";
    copy.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy`;
    copy.onclick = () => {
        const tmp = document.createElement("div"); tmp.innerHTML = text;
        navigator.clipboard.writeText(tmp.textContent || text).then(() => {
            copy.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> Copied!`;
            copy.classList.add("fb-copied");
            setTimeout(() => {
                copy.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy`;
                copy.classList.remove("fb-copied");
            }, 2000);
        });
    };
    bar.appendChild(like); bar.appendChild(dislike); bar.appendChild(regen); bar.appendChild(copy);
    return bar;
}

// ── Weather card ───────────────────────────────────────────────
const WICONS = {"clear sky":"☀️","mainly clear":"🌤️","partly cloudy":"⛅","overcast":"☁️","foggy":"🌫️","light drizzle":"🌦️","drizzle":"🌧️","light rain":"🌦️","rain":"🌧️","heavy rain":"⛈️","light snow":"🌨️","snow":"❄️","showers":"🌧️","thunderstorm":"⛈️"};
function wIcon(c) { const k=(c||"").toLowerCase(); for(const[key,val] of Object.entries(WICONS)) if(k.includes(key)) return val; return "🌡️"; }
function parseWeatherCard(text) {
    if (!text.includes("[WEATHER_CARD]")) return null;
    const m = text.match(/\[WEATHER_CARD\]([\s\S]*?)\[\/WEATHER_CARD\]/);
    if (!m) return null;
    const d = {};
    m[1].trim().split("\n").forEach(l => { const[k,...v]=l.split("="); if(k&&v.length) d[k.trim()]=v.join("=").trim(); });
    return d;
}
function buildWeatherCard(d) {
    const now  = new Date();
    const date = now.toLocaleDateString("en-US",{weekday:"long",month:"long",day:"numeric",year:"numeric"});
    const time = now.toLocaleTimeString("en-US",{hour:"2-digit",minute:"2-digit"});
    return `<div class="weather-card">
  <div class="wc-header"><div><div class="wc-location">${d.city||"?"}</div><div class="wc-country">${d.country||""}</div></div><div class="wc-date">${date}<br/>${time}</div></div>
  <div class="wc-main"><div class="wc-icon">${wIcon(d.condition)}</div><div class="wc-temp-big">${Math.round(d.temp||0)}<sup>°C</sup></div><div><div class="wc-condition">${d.condition||""}</div><div class="wc-feels">Feels like ${Math.round(d.feels_like||0)}°C</div></div></div>
  <div class="wc-stats"><div class="wc-stat"><div class="wc-stat-val">${d.humidity||0}%</div><div class="wc-stat-label">Humidity</div></div><div class="wc-stat"><div class="wc-stat-val">${d.wind||0} km/h</div><div class="wc-stat-label">Wind</div></div><div class="wc-stat"><div class="wc-stat-val">${Math.round(d.feels_like||0)}°C</div><div class="wc-stat-label">Feels Like</div></div></div>
  <div class="wc-hl"><div class="wc-hl-item"><span class="wc-hl-label">↑ High</span><span class="wc-hl-val high">${d.high||"--"}°</span></div><div class="wc-hl-item"><span class="wc-hl-label">↓ Low</span><span class="wc-hl-val low">${d.low||"--"}°</span></div></div>
  ${d.advice?`<div class="wc-advice">💡 ${d.advice}</div>`:""}
</div>`;
}

// ── Markdown renderer ──────────────────────────────────────────
function renderMarkdown(text) {
    const MERMAID_KW = /^[ \t]*(flowchart|sequenceDiagram|classDiagram|erDiagram|gantt|pie|gitGraph|stateDiagram|journey|mindmap)/m;
    if (!text.includes("```mermaid") && MERMAID_KW.test(text)) {
        text = "```mermaid\n" + text.trim() + "\n```";
    }
    text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, url) => {
        if (url.startsWith("data:image")) return _;
        return alt ? `[${alt}]` : "";
    });

    text = text.replace(/```(\w+)?\s*\n?([\s\S]*?)```/g, (_, lang, code) => {
        const l = lang || "plaintext";
        if (l === "mermaid") {
            const id  = "mermaid-" + Math.random().toString(36).slice(2);
            const safe = code.trim().replace(/"/g, "&quot;");
            return `<div class="mermaid-wrap">
                <div class="mermaid-header">
                    <span>📊 Diagram</span>
                    <button class="copy-btn" onclick="navigator.clipboard.writeText(document.getElementById('${id}').dataset.code||'')">Copy</button>
                </div>
                <div class="mermaid-container" id="${id}" data-code="${safe}"></div>
            </div>`;
        }
        const id = "c" + Math.random().toString(36).slice(2);
        return `<div class="code-block"><div class="code-header"><span>${l}</span><button class="copy-btn" onclick="copyCode('${id}')">Copy</button></div><pre><code id="${id}" class="language-${l}">${escapeHtml(code.trim())}</code></pre></div>`;
    });
    text = text.replace(/`([^`]+)`/g,"<code>$1</code>");
    text = text.replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>").replace(/\*(.+?)\*/g,"<em>$1</em>");
    text = text.replace(/^### (.+)$/gm,"<h3>$1</h3>").replace(/^## (.+)$/gm,"<h2>$1</h2>").replace(/^# (.+)$/gm,"<h1>$1</h1>");
    text = text.replace(/^\s*[-*] (.+)$/gm,"<li>$1</li>").replace(/(<li>[\s\S]*?<\/li>)/g,"<ul>$1</ul>");
    text = text.replace(/^\d+\. (.+)$/gm,"<li>$1</li>");
    text = text.split(/\n\n+/).map(p => p.startsWith("<h")||p.startsWith("<ul")||p.startsWith("<div") ? p : `<p>${p.replace(/\n/g,"<br/>")}</p>`).join("");
    return text;
}
function escapeHtml(t) { return t.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

async function renderMermaidBlocks(container) {
    const blocks = container.querySelectorAll(".mermaid-container");
    for (const block of blocks) {
        if (block.dataset.rendered) continue;
        const code = block.dataset.code || "";
        if (!code) continue;
        try {
            block.dataset.rendered = "1";
            const id = "mg-" + Math.random().toString(36).slice(2);
            const { svg } = await mermaid.render(id, code);
            block.innerHTML = svg;
            const svgEl = block.querySelector("svg");
            if (svgEl) {
                svgEl.style.maxWidth = "100%";
                svgEl.style.height  = "auto";
            }
        } catch(e) {
            console.warn("Mermaid render failed:", e);
            block.innerHTML = `<pre style="color:var(--tx2);font-size:12px;padding:12px;overflow-x:auto">${escapeHtml(code)}</pre>`;
        }
    }
    const box = document.getElementById("messages");
    if (box) box.scrollTop = box.scrollHeight;
}
function copyCode(id) {
    const el = document.getElementById(id); if(!el) return;
    navigator.clipboard.writeText(el.textContent).then(() => {
        const b = el.closest(".code-block").querySelector(".copy-btn");
        b.textContent = "Copied!"; setTimeout(() => b.textContent = "Copy", 2000);
    });
}

// ── Typing indicator ───────────────────────────────────────────
function showTyping() {
    const box=document.getElementById("messages"), id="t"+Date.now();
    const row=document.createElement("div"); row.className="msg-row bot"; row.id=id;
    const av=document.createElement("div"); av.className="avatar bot-av"; av.innerHTML=BOT_AVATAR_SVG;
    const bub=document.createElement("div"); bub.className="bubble bot-bubble";
    bub.innerHTML='<div class="typing"><span></span><span></span><span></span></div>';
    row.appendChild(av); row.appendChild(bub); box.appendChild(row);
    box.scrollTop=box.scrollHeight; return id;
}
function removeTyping(id) { document.getElementById(id)?.remove(); }

// ══════════════════════════════════════════════════════════════
// DOCUMENT UPLOAD (PDF/TXT)
// ══════════════════════════════════════════════════════════════
function updateRagStatus(a) {
    document.getElementById("rag-dot")?.classList.toggle("on",a);
    const l=document.getElementById("rag-label"); if(l) l.textContent=a?"RAG Active ✓":"RAG Off";
}
async function uploadFile(file) {
    if (!file) return;
    const typingId = showTyping();
    const fd = new FormData(); fd.append("file", file);
    try {
        const res  = await fetch(`${API}/upload`, {method:"POST", body:fd});
        const data = await res.json();
        removeTyping(typingId);
        const msg = data.success ? `✅ **${file.name}** uploaded successfully! ${data.message}` : `⚠️ ${data.error}`;
        appendBubble(msg, "bot", true);
        if (data.success) { loadDocumentList(); updateRagStatus(true); }
    } catch {
        removeTyping(typingId);
        appendBubble("⚠️ File upload failed.", "bot", true);
    }
    document.getElementById("input-file-pdf").value = "";
}
async function loadDocumentList() {
    try {
        const r = await fetch(`${API}/documents`);
        const d = await r.json();
        updateRagStatus((d.documents||[]).length > 0);
    } catch(e){}
}

// ══════════════════════════════════════════════════════════════
// VOICE (dictation into the message box + read-aloud for chat)
// ══════════════════════════════════════════════════════════════
function initVoice() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    recognition = new SR(); recognition.lang="en-US"; recognition.continuous=false; recognition.interimResults=true;
    recognition.onstart  = () => { isListening=true; setMicState(true); stopSpeaking(); };
    recognition.onresult = (e) => {
        let f="",i="";
        for(let j=e.resultIndex;j<e.results.length;j++){const t=e.results[j][0].transcript; e.results[j].isFinal?(f+=t):(i+=t);}
        const inp=document.getElementById("user-input"); inp.value=f||i; autoResize(inp);
    };
    recognition.onend = () => { isListening=false; setMicState(false); const t=document.getElementById("user-input").value.trim(); if(t) sendMessage(); };
    recognition.onerror = () => { isListening=false; setMicState(false); };
}
function toggleMic() { if(!recognition) return; isListening?recognition.stop():(()=>{document.getElementById("user-input").value="";updateActionBtn();recognition.start();})(); }
function setMicState(a) { document.getElementById("mic-btn")?.classList.toggle("listening",a); document.getElementById("mic-ring")?.classList.toggle("active",a); }
function speak(text) {
    if(!ttsEnabled||!window.speechSynthesis) return; stopSpeaking();
    const clean=text
        .replace(/```[\s\S]*?```/g,"code.")
        .replace(/`[^`]+`/g,"")
        .replace(/\*\*(.+?)\*\*/g,"$1")
        .replace(/\*(.+?)\*/g,"$1")
        .replace(/#{1,3} /g,"")
        .replace(/\[WEATHER_CARD\][\s\S]*?\[\/WEATHER_CARD\]/g,"Weather shown.")
        .replace(/\[IMAGE\][\s\S]*?\[\/IMAGE\]/g,"Image generated.")
        .replace(/!\[([^\]]*)\]\([^)]+\)/g,"")
        .replace(/\n+/g," ").trim();
    const u=new SpeechSynthesisUtterance(clean); u.lang="en-US";
    const v=window.speechSynthesis.getVoices().find(v=>v.name.includes("Google")||v.name.includes("Natural")); if(v) u.voice=v;
    u.onstart=()=>document.getElementById("tts-btn")?.classList.add("speaking");
    u.onend=()=>document.getElementById("tts-btn")?.classList.remove("speaking");
    window.speechSynthesis.speak(u);
}
function stopSpeaking() { if(window.speechSynthesis) window.speechSynthesis.cancel(); document.getElementById("tts-btn")?.classList.remove("speaking"); }
function toggleTTS() { ttsEnabled=!ttsEnabled; document.getElementById("tts-btn")?.classList.toggle("muted",!ttsEnabled); if(!ttsEnabled) stopSpeaking(); }
if(window.speechSynthesis) window.speechSynthesis.onvoiceschanged=()=>window.speechSynthesis.getVoices();

// ══════════════════════════════════════════════════════════════
// CALL MODE — full-screen voice conversation (like ChatGPT voice)
// ══════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// CALL MODE — full-screen voice conversation (like ChatGPT voice)
// Natural neural voice from the backend (/api/tts); falls back to the browser voice.
// ══════════════════════════════════════════════════════════════
let callActive      = false;
let callMuted       = false;
let callRecognition = null;
let callState       = "idle";            // listening | thinking | speaking | muted
let callLang        = localStorage.getItem("nb_call_lang")   || "en-US";
let callGender      = localStorage.getItem("nb_call_gender") || "female";
let callAbort       = null;              // AbortController of the running chat request
let callSpeakQueue  = 0;                 // sentences waiting to be / being spoken
let callStreamDone  = true;              // true when the reply has fully arrived
let callRunId       = 0;                 // changes every turn; stale callbacks check it

// natural-voice playback
let callAudio         = null;            // ONE <audio> element reused for every sentence (also works on iPhone)
let callAudioResolve  = null;
let callBrowserResolve = null;
let callTtsQueue      = [];              // [{text, lang, runId, promise}]
let callTtsBusy       = false;
let callTtsCtrl       = null;            // aborts pending /api/tts requests
let callTtsFails      = 0;
let callTtsDown       = false;           // after 2 failures in a row → use the browser voice

const SILENT_WAV = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=";
const CALL_NON_LATIN = new Set(["ur-PK","ar-SA","fa-IR","hi-IN","bn-BD","zh-CN","ja-JP","ko-KR","ru-RU"]);

const CALL_TEXT = {
    "en": { note: "I've put it in the chat.",            err: "Sorry, I couldn't reach the server." },
    "ur": { note: "میں نے یہ چیٹ میں دکھا دیا ہے۔",        err: "معذرت، سرور سے رابطہ نہیں ہو سکا۔" },
    "ar": { note: "لقد عرضته في المحادثة.",                err: "عذراً، تعذر الاتصال بالخادم." },
    "hi": { note: "मैंने इसे चैट में दिखा दिया है।",          err: "माफ़ कीजिए, सर्वर से संपर्क नहीं हो सका।" },
    "es": { note: "Lo he mostrado en el chat.",            err: "Lo siento, no pude conectar con el servidor." },
    "fr": { note: "Je l'ai affiché dans le chat.",         err: "Désolé, je n'ai pas pu joindre le serveur." },
    "tr": { note: "Bunu sohbette gösterdim.",              err: "Üzgünüm, sunucuya ulaşılamadı." },
    "de": { note: "Ich habe es im Chat angezeigt.",        err: "Entschuldigung, der Server ist nicht erreichbar." }
};
function callText(kind) {
    const t = CALL_TEXT[callLang.split("-")[0]] || CALL_TEXT["en"];
    return t[kind];
}

// ── Start / end ────────────────────────────────────────────────
function startCallMode() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
        alert("Voice conversation needs Chrome or Edge. This browser does not support speech recognition.");
        return;
    }
    stopSpeaking();
    callActive = true;
    callMuted  = false;
    callTtsFails = 0;
    callTtsDown  = false;
    unlockCallAudio();                       // must happen inside the tap so the browser allows sound later
    const sel = document.getElementById("call-lang-select");
    if (sel) sel.value = callLang;
    const gsel = document.getElementById("call-gender-select");
    if (gsel) gsel.value = callGender;
    updateMuteBtn();
    document.getElementById("call-transcript").textContent = "";
    document.getElementById("call-screen").style.display = "flex";
    document.getElementById("welcome")?.remove();
    callListenOnce();
}

function endCallMode() {
    callActive = false;
    callRunId++;
    stopCallRecognition();
    if (callAbort) { try { callAbort.abort(); } catch {} callAbort = null; }
    resetCallAudio();
    document.getElementById("call-screen").style.display = "none";
}

function setCallLanguage(lang) {
    callLang = lang;
    localStorage.setItem("nb_call_lang", lang);
    if (callActive && callState === "listening") callListenOnce();   // restart in the new language
}

function setCallGender(g) {
    callGender = (g === "male") ? "male" : "female";
    localStorage.setItem("nb_call_gender", callGender);
}

// ── UI state ───────────────────────────────────────────────────
function setCallState(state, text) {
    callState = state;
    const orb = document.getElementById("call-orb");
    if (orb) {
        orb.classList.remove("listening", "thinking", "speaking", "muted");
        orb.classList.add(state);
    }
    const labels = {
        listening: "Listening…",
        thinking:  "Thinking…",
        speaking:  "Speaking… tap the orb to interrupt",
        muted:     "Microphone is muted"
    };
    const st = document.getElementById("call-status");
    if (st) st.textContent = text || labels[state] || "";
}

function updateMuteBtn() {
    document.getElementById("call-mute-btn")?.classList.toggle("off", callMuted);
}

function toggleCallMute() {
    callMuted = !callMuted;
    updateMuteBtn();
    if (callMuted) {
        stopCallRecognition();
        if (callState === "listening") setCallState("muted");
    } else if (callState === "muted") {
        callListenOnce();
    }
}

// Tap the orb while the bot is thinking or speaking → stop it and listen again
function callOrbTap() {
    if (!callActive) return;
    if (callState === "speaking" || callState === "thinking") {
        callRunId++;
        if (callAbort) { try { callAbort.abort(); } catch {} callAbort = null; }
        resetCallAudio();
        callStreamDone = true;
        callListenOnce();
    }
}

// ── Listening ──────────────────────────────────────────────────
function stopCallRecognition() {
    if (!callRecognition) return;
    callRecognition.onresult = null;
    callRecognition.onerror  = null;
    callRecognition.onend    = null;
    try { callRecognition.abort(); } catch {}
    callRecognition = null;
}

function callListenOnce() {
    if (!callActive) return;
    stopCallRecognition();
    if (callMuted) { setCallState("muted"); return; }

    const SR  = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR();
    callRecognition = rec;
    rec.lang            = callLang;
    rec.continuous      = false;
    rec.interimResults  = true;
    rec.maxAlternatives = 1;

    setCallState("listening");
    document.getElementById("call-transcript").textContent = "";

    let finalText = "", lastInterim = "", errCode = "";

    rec.onresult = (e) => {
        let interim = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
            const t = e.results[i][0].transcript;
            if (e.results[i].isFinal) finalText += t; else interim += t;
        }
        lastInterim = interim;
        document.getElementById("call-transcript").textContent = (finalText + " " + interim).trim();
    };

    rec.onerror = (e) => { errCode = (e && e.error) || "error"; };

    rec.onend = () => {
        if (!callActive || callRecognition !== rec) return;
        callRecognition = null;

        if (errCode === "not-allowed" || errCode === "service-not-allowed") {
            setCallState("listening", "Microphone is blocked. Allow microphone access for this site, then start the call again.");
            return;
        }
        if (errCode === "language-not-supported") {
            setCallState("listening", "This browser cannot recognise the selected language. Pick another language or use Chrome.");
            return;
        }

        const text = (finalText.trim() || lastInterim.trim());
        if (text) { callSendAndReply(text); return; }

        // nothing heard → listen again (slower retry if there was a real error)
        const delay = (!errCode || errCode === "no-speech") ? 150 : 1500;
        setTimeout(() => { if (callActive && !callMuted && callState === "listening") callListenOnce(); }, delay);
    };

    try { rec.start(); }
    catch { setTimeout(() => { if (callActive) callListenOnce(); }, 500); }
}

// ── Sending + speaking sentence by sentence ────────────────────
async function callSendAndReply(text) {
    const myRun = ++callRunId;
    resetCallAudio();
    callTtsCtrl    = new AbortController();
    callStreamDone = false;
    setCallState("thinking");
    document.getElementById("call-transcript").textContent = text;

    const sendTime = new Date().toLocaleTimeString("en-US", {hour:"2-digit", minute:"2-digit"});
    messages.push({role:"user", content:text, time:sendTime});
    appendBubble(text, "user", true, sendTime);

    const safeMessages = messages.map(m => {
        if (!m.content) return m;
        if (m.content.includes("[IMAGE]") || m.content.includes("data:image") || m.content.includes("[Image was generated]")) {
            return {...m, content: "[Image was generated]"};
        }
        if (m.content.length > 4000) return {...m, content: m.content.slice(0, 4000)};
        return m;
    });

    const ctrl = new AbortController();
    callAbort = ctrl;

    let fullReply = "", sentenceBuf = "", speakBuf = "";
    let codeNoted = false, failed = false, inCodeBlock = false, spokeFirst = false;

    // the first chunk is short (fast start); later chunks are longer (smoother voice)
    const speakPart = (s) => {
        speakBuf += (speakBuf ? " " : "") + s;
        if (speakBuf.length >= (spokeFirst ? 45 : 20)) {
            enqueueSpeech(speakBuf, myRun);
            speakBuf = ""; spokeFirst = true;
        }
    };

    try {
        const res = await fetch(`${API}/chat`, {
            method: "POST", headers: authH(), signal: ctrl.signal,
            body: JSON.stringify({messages: safeMessages, session_id: currentSid, stream: true})
        });
        if (!res.ok || !res.body) throw new Error("HTTP " + res.status);

        const reader  = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            const lines = buf.split("\n");
            buf = lines.pop();                           // keep the unfinished last line
            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                let ev; try { ev = JSON.parse(line.slice(6)); } catch { continue; }
                if (ev.type !== "token" || !ev.text) continue;

                fullReply += ev.text;
                if (fullReply.includes("[IMAGE]") || fullReply.includes("[WEATHER_CARD]")) continue;

                // walk through the token, switching in/out of code blocks at every ```
                const segs = ev.text.split("```");
                for (let i = 0; i < segs.length; i++) {
                    if (i > 0) {
                        inCodeBlock = !inCodeBlock;
                        if (inCodeBlock) {               // a code block just started: never read code aloud
                            if (sentenceBuf.trim()) speakPart(sentenceBuf.trim());
                            sentenceBuf = "";
                            if (!codeNoted) { codeNoted = true; speakPart(callText("note")); }
                        }
                    }
                    if (!inCodeBlock) sentenceBuf += segs[i];
                }
                const parts = splitSentences(sentenceBuf);
                sentenceBuf = parts.rest;
                parts.sentences.forEach(speakPart);
            }
        }
    } catch (e) {
        if (!e || e.name !== "AbortError") failed = true;
    }

    if (callAbort === ctrl) callAbort = null;
    const stale   = (myRun !== callRunId);
    const special = fullReply.includes("[IMAGE]") || fullReply.includes("[WEATHER_CARD]");

    if (!stale && callActive) {
        if (special)             enqueueSpeech(callText("note"), myRun);
        else {
            const tail = (speakBuf + " " + sentenceBuf).trim();
            if (tail)            enqueueSpeech(tail, myRun);
        }
        if (failed && !fullReply) enqueueSpeech(callText("err"), myRun);
    }

    // keep the conversation in the chat (even a partial reply if the user interrupted)
    const reply = fullReply.trim();
    if (reply) {
        const stored = (reply.includes("[IMAGE]") || reply.includes("data:image")) ? "[Image was generated]" : reply;
        messages.push({role:"assistant", content: stored});
        appendBubble(reply, "bot", true);
    } else if (failed) {
        appendBubble("⚠️ Could not reach the server. Please try again.", "bot", true);
    }
    const s = sessions.find(s => s.id === currentSid);
    if (s && s.title === "New Chat") { s.title = text.length > 45 ? text.slice(0, 45) + "…" : text; renderHistory(); }

    if (stale || !callActive) return;
    callStreamDone = true;
    callMaybeResume(myRun);
}

function callMaybeResume(runId) {
    if (!callActive || runId !== callRunId) return;
    if (callState === "listening" && callRecognition) return;       // already listening
    if (callStreamDone && callSpeakQueue === 0) callListenOnce();
}

// ── Natural voice playback ─────────────────────────────────────
function unlockCallAudio() {
    if (!callAudio) callAudio = new Audio();
    try {
        callAudio.src = SILENT_WAV;
        const p = callAudio.play();
        if (p && p.catch) p.catch(() => {});
    } catch {}
}

function resetCallAudio() {
    callTtsQueue = [];
    if (callTtsCtrl) { try { callTtsCtrl.abort(); } catch {} callTtsCtrl = null; }
    stopCallAudio();
    callSpeakQueue = 0;
}

function stopCallAudio() {
    if (callAudio) { try { callAudio.pause(); } catch {} }
    if (callAudioResolve)   callAudioResolve(true);
    if (callBrowserResolve) callBrowserResolve();
    if (window.speechSynthesis) window.speechSynthesis.cancel();
}

async function ttsFetch(text, lang, signal) {
    const res = await fetch(`${API}/tts`, {
        method: "POST", signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, lang, gender: callGender })
    });
    if (!res.ok) throw new Error("tts " + res.status);
    const blob = await res.blob();
    if (!blob || !blob.size) throw new Error("empty audio");
    return URL.createObjectURL(blob);
}

// Queue one chunk of text. The audio is requested right away, so the next chunk is ready while this one plays.
function enqueueSpeech(raw, runId) {
    if (!callActive || runId !== callRunId) return;
    const clean = cleanForSpeech(raw);
    if (!clean) return;

    const lang = detectSpeechLang(clean);
    const item = { text: clean, lang, runId, promise: null };
    if (!callTtsDown) {
        item.promise = ttsFetch(clean, lang, callTtsCtrl ? callTtsCtrl.signal : undefined)
            .then(url => { callTtsFails = 0; return url; })
            .catch(err => {
                if (!err || err.name !== "AbortError") { callTtsFails++; if (callTtsFails >= 2) callTtsDown = true; }
                return null;
            });
    }
    callSpeakQueue++;
    callTtsQueue.push(item);
    if (!callTtsBusy) playNextTts();
}

async function playNextTts() {
    if (callTtsBusy) return;
    callTtsBusy = true;
    while (callTtsQueue.length) {
        const item = callTtsQueue.shift();
        if (!callActive || item.runId !== callRunId) continue;                 // belongs to an interrupted turn

        const url = item.promise ? await item.promise : null;
        if (!callActive || item.runId !== callRunId) { if (url) URL.revokeObjectURL(url); continue; }

        let played = false;
        if (url) played = await playUrl(url, item);
        if (!played && callActive && item.runId === callRunId) await speakWithBrowser(item);   // fallback voice

        if (item.runId === callRunId) callSpeakQueue = Math.max(0, callSpeakQueue - 1);
    }
    callTtsBusy = false;
    callMaybeResume(callRunId);
}

// resolves true when the audio played (or was stopped), false if the browser refused to play it
function playUrl(url, item) {
    return new Promise((resolve) => {
        if (!callAudio) callAudio = new Audio();
        const a = callAudio;
        let done = false, guard = null;
        const finish = (ok) => {
            if (done) return; done = true;
            clearTimeout(guard);
            a.onplay = a.onended = a.onerror = null;
            if (callAudioResolve === finish) callAudioResolve = null;
            URL.revokeObjectURL(url);
            resolve(ok);
        };
        callAudioResolve = finish;
        guard = setTimeout(() => finish(true), 60000);
        a.onplay  = () => {
            if (item.runId !== callRunId) return;
            setCallState("speaking");
            document.getElementById("call-transcript").textContent = item.text;
        };
        a.onended = () => finish(true);
        a.onerror = () => finish(false);
        a.src = url;
        const p = a.play();
        if (p && p.catch) p.catch(() => finish(false));
    });
}

// fallback: the browser's own voice
function speakWithBrowser(item) {
    return new Promise((resolve) => {
        if (!window.speechSynthesis) { resolve(); return; }
        const u = new SpeechSynthesisUtterance(item.text);
        u.lang = item.lang;
        const v = pickVoice(item.lang);
        if (v) u.voice = v;
        let done = false, guard = null;
        const finish = () => {
            if (done) return; done = true;
            clearTimeout(guard);
            if (callBrowserResolve === finish) callBrowserResolve = null;
            resolve();
        };
        callBrowserResolve = finish;
        guard = setTimeout(finish, 30000);
        u.onstart = () => {
            if (item.runId !== callRunId) return;
            setCallState("speaking");
            document.getElementById("call-transcript").textContent = item.text;
        };
        u.onend = finish;
        u.onerror = finish;
        window.speechSynthesis.speak(u);
    });
}

// ── Text → speech helpers ──────────────────────────────────────
// Splits streamed text into finished sentences. Works for . ! ? ۔ ؟ । and 。！？
function splitSentences(buf) {
    const re = /[^.!?۔؟।\n]*[.!?۔؟।]+(?=\s)|[^。！？\n]*[。！？]+|[^\n]*\n/g;
    const sentences = [];
    let m, last = 0;
    while ((m = re.exec(buf)) !== null) {
        if (m[0] === "") { re.lastIndex++; continue; }
        const s = m[0].trim();
        if (s) sentences.push(s);
        last = re.lastIndex;
    }
    return { sentences, rest: buf.slice(last) };
}

function cleanForSpeech(t) {
    return t
        .replace(/```[\s\S]*?```/g, " ")
        .replace(/`([^`]*)`/g, "$1")
        .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
        .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
        .replace(/https?:\/\/\S+/g, " ")
        .replace(/\[\/?(WEATHER_CARD|IMAGE)\]/g, " ")
        .replace(/^\s{0,3}#{1,6}\s*/gm, "")
        .replace(/^\s*[-*•]\s+/gm, "")
        .replace(/^\s*\d+[.)]\s+/gm, "")
        .replace(/[*_~>|]+/g, " ")
        .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, " ")
        .replace(/\s+/g, " ")
        .trim();
}

// Pick the speaking language from the script of the reply, so the right voice is used
function detectSpeechLang(t) {
    if (/[\u0600-\u06FF]/.test(t)) {
        if (/[\u0679\u0688\u0691\u06BA\u06D2\u06BE\u06C1]/.test(t)) return "ur-PK";
        return ["ar-SA", "fa-IR", "ur-PK"].includes(callLang) ? callLang : "ar-SA";
    }
    if (/[\u0900-\u097F]/.test(t)) return "hi-IN";
    if (/[\u0980-\u09FF]/.test(t)) return "bn-BD";
    if (/[\u3040-\u30FF]/.test(t)) return "ja-JP";
    if (/[\uAC00-\uD7AF]/.test(t)) return "ko-KR";
    if (/[\u4E00-\u9FFF]/.test(t)) return "zh-CN";
    if (/[\u0400-\u04FF]/.test(t)) return "ru-RU";
    return CALL_NON_LATIN.has(callLang) ? "en-US" : callLang;   // Latin text
}

// browser-voice picker (only used by the fallback)
function pickVoice(lang) {
    if (!window.speechSynthesis) return null;
    const voices = window.speechSynthesis.getVoices();
    if (!voices || !voices.length) return null;
    const want  = lang.toLowerCase();
    const exact = voices.filter(v => (v.lang || "").replace("_", "-").toLowerCase() === want);
    const base  = voices.filter(v => (v.lang || "").toLowerCase().startsWith(want.split("-")[0]));
    const pool  = exact.length ? exact : base;
    if (!pool.length) return null;
    return pool.find(v => /natural|online/i.test(v.name))
        || pool.find(v => /google/i.test(v.name))
        || pool[0];
}

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && callActive) endCallMode();
});
// ══════════════════════════════════════════════════════════════
// UTILS
// ══════════════════════════════════════════════════════════════
function handleKey(e) { if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendMessage();} }

function autoResize(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 180) + "px";
    updateActionBtn();
}

// ChatGPT-style button: waveform when the box is empty, send arrow when there is text
function updateActionBtn() {
    const input = document.getElementById("user-input");
    const btn   = document.getElementById("send-btn");
    if (!input || !btn) return;
    const has = input.value.trim().length > 0;
    btn.classList.toggle("is-wave", !has);
    btn.title = has ? "Send message" : "Start voice conversation";
    const w = document.getElementById("icon-wave");
    const s = document.getElementById("icon-send");
    if (w) w.style.display = has ? "none"  : "block";
    if (s) s.style.display = has ? "block" : "none";
}
function handleActionBtn() {
    const has = document.getElementById("user-input").value.trim().length > 0;
    has ? sendMessage() : startCallMode();
}

function toggleSidebar() {
    const isMobile = window.innerWidth <= 768;
    const sidebar  = document.getElementById("sidebar");
    if (!sidebar) return;
    if (isMobile) {
        const isOpen = sidebar.classList.contains("open");
        isOpen ? closeSidebar() : openSidebar();
    } else {
        sidebar.classList.toggle("hidden");
    }
}

// ══════════════════════════════════════════════════════════════
// DARK / LIGHT MODE TOGGLE
// ══════════════════════════════════════════════════════════════
function toggleTheme() {
    const isLight = document.body.classList.toggle('light-mode');
    localStorage.setItem('nexus_theme', isLight ? 'light' : 'dark');
    const btn = document.getElementById('theme-btn');
    if (btn) btn.innerHTML = isLight
        ? `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg> Theme`
        : `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg> Theme`;
}

(function applyTheme() {
    if (localStorage.getItem('nexus_theme') === 'light')
        document.body.classList.add('light-mode');
})();

// ══════════════════════════════════════════════════════════════
// MOBILE SIDEBAR
// ══════════════════════════════════════════════════════════════
function openSidebar() {
    document.getElementById('sidebar').classList.add('open');
    document.getElementById('sidebar-overlay').classList.add('show');
}
function closeSidebar() {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebar-overlay').classList.remove('show');
}

// ══════════════════════════════════════════════════════════════
// MESSAGE EDITING
// ══════════════════════════════════════════════════════════════
function editMessage(msgIndex) {
    const userRows = document.querySelectorAll('.msg-row.user');
    const row      = userRows[msgIndex];
    if (!row) return;
    const origText = row.querySelector('.user-bubble')?.dataset?.userText
                  || row.querySelector('.user-bubble')?.textContent?.trim()
                  || "";
    const wrap = row.querySelector('.user-msg-wrap') || row.querySelector('.user-bubble-outer') || row.querySelector('.bubble');
    if (!wrap) return;
    wrap.dataset.origText = origText;
    wrap.innerHTML = "";
    const ta = document.createElement("textarea");
    ta.className = "edit-area";
    ta.id = "edit-area-" + msgIndex;
    ta.rows = 3;
    ta.value = origText;
    wrap.appendChild(ta);
    const acts = document.createElement("div");
    acts.className = "edit-actions";
    acts.innerHTML = `
        <button class="edit-save-btn" onclick="saveEdit(${msgIndex})">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            Send
        </button>
        <button class="edit-cancel-btn" onclick="cancelEdit(${msgIndex})">Cancel</button>`;
    wrap.appendChild(acts);
    ta.focus();
    ta.style.height = "auto";
    ta.style.height = ta.scrollHeight + "px";
}
function cancelEdit(msgIndex) {
    const userRows = document.querySelectorAll('.msg-row.user');
    const row      = userRows[msgIndex];
    if (!row) return;
    const wrap     = row.querySelector('.user-msg-wrap') || row.querySelector('.user-bubble-outer') || row.querySelector('.bubble');
    if (!wrap) return;
    const origText = wrap.dataset.origText || messages[msgIndex * 2]?.content || "";
    wrap.innerHTML = "";
    const msgDiv  = document.createElement("div");
    msgDiv.className = "user-bubble";
    msgDiv.textContent = origText;
    msgDiv.dataset.userText = origText;
    wrap.appendChild(msgDiv);
    const timeStr = messages[msgIndex * 2]?.time || "";
    const actBar  = document.createElement("div");
    actBar.className = "user-action-bar";
    actBar.innerHTML = `<span class="msg-time">${timeStr}</span>`;
    const eb = document.createElement("button");
    eb.className = "ua-btn"; eb.title = "Edit message";
    eb.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> Edit`;
    eb.onclick = () => editMessage(msgIndex);
    actBar.appendChild(eb);
    const cb = document.createElement("button");
    cb.className = "ua-btn"; cb.title = "Copy";
    cb.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy`;
    cb.onclick = () => navigator.clipboard.writeText(origText).then(() => { cb.textContent = "Copied!"; setTimeout(() => { cb.textContent = "Copy"; }, 1500); });
    actBar.appendChild(cb);
    wrap.appendChild(actBar);
}
async function saveEdit(msgIndex) {
    const ta = document.getElementById(`edit-area-${msgIndex}`);
    if (!ta) return;
    const newText = ta.value.trim();
    if (!newText) return;
    const allRows = Array.from(document.querySelectorAll('.msg-row'));
    const userRows = document.querySelectorAll('.msg-row.user');
    const editedRow = userRows[msgIndex];
    let removing = false;
    allRows.forEach(row => {
        if (row === editedRow) removing = true;
        if (removing) row.remove();
    });
    const msgArrayIndex = msgIndex * 2;
    messages = messages.slice(0, msgArrayIndex);
    const input = document.getElementById('user-input');
    input.value = newText;
    await sendMessage();
}

// ══════════════════════════════════════════════════════════════
// EXPORT CHAT
// ══════════════════════════════════════════════════════════════
function exportChat() {
    if (!messages || messages.length === 0) {
        alert('No messages to export.');
        return;
    }
    let text = `NexusBot — Chat Export\n${'='.repeat(40)}\n\n`;
    messages.forEach(m => {
        const role = m.role === 'user' ? 'You' : 'NexusBot';
        const content = m.content
            .replace(/\[IMAGE\].*?\[\/IMAGE\]/gs, '[Generated Image]')
            .replace(/\[WEATHER_CARD\].*?\[\/WEATHER_CARD\]/gs, '[Weather Card]');
        text += `${role}:\n${content}\n\n${'─'.repeat(30)}\n\n`;
    });
    const blob = new Blob([text], { type: 'text/plain' });
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = `nexusbot-chat-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
}

// ══════════════════════════════════════════════════════════════
// PATCH appendBubble — add Edit button after DOM settles
function _addEditButton() {
    const userRows = document.querySelectorAll('.msg-row.user');
    const lastRow  = userRows[userRows.length - 1];
    if (!lastRow) return;
    if (lastRow.querySelector('.edit-btn')) return;
    const idx = userRows.length - 1;
    const bar = lastRow.querySelector('.feedback-bar');
    if (bar) {
        const editBtn = document.createElement('button');
        editBtn.className = 'edit-btn';
        editBtn.title = 'Edit message';
        editBtn.innerHTML = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> Edit`;
        editBtn.onclick = () => editMessage(idx);
        bar.insertBefore(editBtn, bar.firstChild);
    }
}