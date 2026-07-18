const attachBtn = document.getElementById("attachBtn");
const fileInput = document.getElementById("fileInput");
const chatWindow = document.getElementById("chatWindow");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const logoutBtn = document.getElementById("logoutBtn");

if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
        // console.log("logging out user...");
        await fetch("/logout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });
        location.reload();
    });
}


function scrollToBottom() {
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function addMessage(role, text, timestamp, sources) {
    const row = document.createElement("div");
    row.className = `row ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "🧑" : "✨";

    const stack = document.createElement("div");
    stack.className = "bubble-stack";

    const label = document.createElement("div");
    label.className = "sender-label";
    label.textContent = role === "user" ? "You" : "Assistant";
    stack.appendChild(label);

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    stack.appendChild(bubble);

    if (sources && sources.length > 0) {
        const sourcesDiv = document.createElement("div");
        sourcesDiv.className = "retrieved-sources";
        
        const title = document.createElement("strong");
        title.textContent = "Sources used:";
        sourcesDiv.appendChild(title);
        
        const ul = document.createElement("ul");
        for (let i = 0; i < sources.length; i++) {
            const s = sources[i];
            const li = document.createElement("li");
            li.innerHTML = "<strong>" + s.filename + " (chunk " + s.chunk_number + ")</strong>";
            ul.appendChild(li);
        }


        sourcesDiv.appendChild(ul);
        stack.appendChild(sourcesDiv);
    }

    if (timestamp) {
        const time = document.createElement("div");
        time.className = "timestamp";
        time.textContent = timestamp;
        stack.appendChild(time);
    }

    row.appendChild(avatar);
    row.appendChild(stack);
    chatWindow.appendChild(row);
    scrollToBottom();
}

function showTyping() {
    const row = document.createElement("div");
    row.className = "row assistant";
    row.id = "typingRow";

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "✨";

    const bubble = document.createElement("div");
    bubble.className = "bubble typing";
    bubble.innerHTML = "<span></span><span></span><span></span>";

    row.appendChild(avatar);
    row.appendChild(bubble);
    chatWindow.appendChild(row);
    scrollToBottom();
}

function hideTyping() {
    const row = document.getElementById("typingRow");
    if (row) row.remove();
}

attachBtn.addEventListener("click", () => {
    fileInput.click();
});

fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;

    addMessage("user", `📎 ${file.name}`);
    attachBtn.classList.add("uploading");
    showTyping();

    // upload file using FormData to the backend
    const formData = new FormData();
    formData.append("file", file);


    try {
        // console.log("sending file to upload endpoint...");
        const res = await fetch("/upload", { method: "POST", body: formData });
        const data = await res.json();
        // console.log("upload response:", data);
        hideTyping();

        if (res.ok) {
            addMessage("assistant", `${data.message} I've indexed ${data.chunks_created} chunks — ask me anything about it.`);
            await loadUserDocuments();
        } else {
            addMessage("assistant", `Upload failed: ${data.error}`);
        }
    } catch (err) {
        console.error(err);
        hideTyping();
        addMessage("assistant", "Upload failed. Check your connection.");
    } finally {

        attachBtn.classList.remove("uploading");
        fileInput.value = "";
    }
});

async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;

    // console.log("sending message:", message);
    addMessage("user", message);
    messageInput.value = "";
    sendBtn.disabled = true;
    showTyping();

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message }),
        });
        const data = await res.json();
        // console.log("got response:", data);
        hideTyping();

        if (res.ok) {
            addMessage("assistant", data.answer, data.timestamp, data.sources);
        } else {
            addMessage("assistant", `Error: ${data.error}`);
        }
    } catch (err) {
        console.error(err);
        hideTyping();
        addMessage("assistant", "Something went wrong. Try again.");
    } finally {

        sendBtn.disabled = false;
    }
}

sendBtn.addEventListener("click", sendMessage);
messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
});

// Document management helper functions
async function loadUserDocuments() {
    try {
        const res = await fetch("/documents");
        if (res.ok) {
            const data = await res.json();
            renderDocumentsList(data.documents);
        }
    } catch (err) {
        console.error("Failed to load documents:", err);
    }
}

async function loadChatHistory() {
    const res = await fetch("/history");
    const data = await res.json();
    const historyList = document.getElementById("historyList");
    if (!historyList) return;

    historyList.innerHTML = "";
    for (let i = 0; i < data.sessions.length; i++) {
        const s = data.sessions[i];
        const item = document.createElement("div");
        item.className = "history-item";
        if (s.id === currentSessionId) item.classList.add("active");
        
        item.innerHTML = '<a href="/history/' + s.id + '/open">' + s.title + '</a>' +
                         '<span class="delete-btn" onclick="deleteHistory(event, \'' + s.id + '\')">×</span>';
        historyList.appendChild(item);
    }
}

function renderDocumentsList(docs) {
    const container = document.getElementById("documentsList");
    if (!container) return;
    
    container.innerHTML = "";
    if (!docs || docs.length === 0) {
        container.innerHTML = '<p class="doc-empty">No files uploaded yet.</p>';
        return;
    }
    for (let i = 0; i < docs.length; i++) {
        const doc = docs[i];
        const div = document.createElement("div");
        div.className = "document-item";
        div.setAttribute("data-filename", doc);
        
        div.innerHTML = '<span class="doc-icon">📄</span>' +
                        '<span class="doc-name" title="' + doc + '">' + doc + '</span>' +
                        '<button type="button" class="delete-doc-btn" onclick="deleteDocument(\'' + doc + '\')" title="Delete document">🗑️</button>';
        container.appendChild(div);
    }
}

async function deleteDocument(filename) {
    if (!confirm('Are you sure you want to delete "' + filename + '"? This will remove its indexed text.')) {
        return;
    }
    try {
        const res = await fetch(`/documents/${encodeURIComponent(filename)}`, {
            method: "DELETE"
        });
        if (res.ok) {
            await loadUserDocuments();
        } else {
            alert("Failed to delete document.");
        }
    } catch (err) {
        console.error("Error deleting document:", err);
        alert("Error deleting document.");
    }
}

// Expose deleteDocument globally for onclick handlers in template
window.deleteDocument = deleteDocument;

// Render initial history messages
for (let i = 0; i < initialMessages.length; i++) {
    const m = initialMessages[i];
    addMessage(m.role, m.text, m.timestamp, m.sources);
}
