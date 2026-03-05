const chatEl = document.getElementById('chat');
const formEl = document.getElementById('chatForm');
const messageEl = document.getElementById('message');
const modelSelectEl = document.getElementById('modelSelect');
const systemPromptEl = document.getElementById('systemPrompt');
const newChatBtn = document.getElementById('newChatBtn');
const fileInputEl = document.getElementById('fileInput');
const filePreviewEl = document.getElementById('filePreview');

let activeSessionId = '';
let attachedFile = null;
let currentModel = '';
// Store conversations per model: { modelName: [{ role, content }] }
let modelConversations = {};

function generateSessionId() {
  if (window.crypto && typeof window.crypto.randomUUID === 'function') {
    return window.crypto.randomUUID();
  }

  if (window.crypto && typeof window.crypto.getRandomValues === 'function') {
    const bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getOrCreateSessionId() {
  // Always create a fresh session on page load for a clean slate
  const id = generateSessionId();
  localStorage.setItem('promptTesterSessionId', id);
  return id;
}

function setSessionId(id) {
  localStorage.setItem('promptTesterSessionId', id);
  activeSessionId = id;
}

function appendMessage(role, content) {
  const item = document.createElement('div');
  item.className = `message ${role}`;
  item.textContent = content;
  chatEl.appendChild(item);
  chatEl.scrollTop = chatEl.scrollHeight;
  
  // Save to current model's conversation
  if (!modelConversations[currentModel]) {
    modelConversations[currentModel] = [];
  }
  modelConversations[currentModel].push({ role, content });
}

function loadModelConversation(model) {
  chatEl.innerHTML = '';
  const messages = modelConversations[model] || [];
  messages.forEach(msg => {
    const item = document.createElement('div');
    item.className = `message ${msg.role}`;
    item.textContent = msg.content;
    chatEl.appendChild(item);
  });
  chatEl.scrollTop = chatEl.scrollHeight;
}

function clearCurrentModelConversation() {
  modelConversations[currentModel] = [];
  chatEl.innerHTML = '';
}

async function clearHistory(sessionId) {
  if (!sessionId) {
    return;
  }

  await fetch(`/api/history/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  });
}

function showFilePreview(file) {
  filePreviewEl.innerHTML = '';
  const item = document.createElement('div');
  item.className = 'filePreviewItem';

  if (file.type.startsWith('image/')) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = document.createElement('img');
      img.src = e.target.result;
      item.appendChild(img);
      addFileInfo(item, file);
    };
    reader.readAsDataURL(file);
  } else {
    addFileInfo(item, file);
  }

  filePreviewEl.appendChild(item);
  filePreviewEl.classList.add('active');
}

function addFileInfo(item, file) {
  const info = document.createElement('div');
  info.className = 'fileInfo';
  info.textContent = `${file.name} (${(file.size / 1024).toFixed(2)} KB)`;
  item.appendChild(info);

  const removeBtn = document.createElement('button');
  removeBtn.className = 'removeBtn';
  removeBtn.type = 'button';
  removeBtn.textContent = 'Remove';
  removeBtn.addEventListener('click', () => {
    attachedFile = null;
    fileInputEl.value = '';
    filePreviewEl.innerHTML = '';
    filePreviewEl.classList.remove('active');
  });
  item.appendChild(removeBtn);
}

fileInputEl.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (file) {
    if (file.size > 20 * 1024 * 1024) {
      alert('File size exceeds 20MB limit');
      fileInputEl.value = '';
      attachedFile = null;
      return;
    }
    attachedFile = file;
    showFilePreview(file);
  } else {
    attachedFile = null;
    filePreviewEl.innerHTML = '';
    filePreviewEl.classList.remove('active');
  }
});

formEl.addEventListener('submit', async (event) => {
  event.preventDefault();
  const message = messageEl.value.trim();
  const sessionId = activeSessionId;
  const model = modelSelectEl ? modelSelectEl.value.trim() : '';
  const systemPrompt = systemPromptEl.value.trim();

  if (!message && !attachedFile) return;
  if (!sessionId) {
    return;
  }

  // Update currentModel to match the selected model
  currentModel = model;

  appendMessage('user', attachedFile ? `${message || '(no text)'} [File: ${attachedFile.name}]` : message);
  messageEl.value = '';
  systemPromptEl.value = '';

  let fileData = null;
  let fileName = null;
  let fileMimeType = null;

  if (attachedFile) {
    const reader = new FileReader();
    fileData = await new Promise((resolve) => {
      reader.onload = () => resolve(reader.result.split(',')[1]);
      reader.readAsDataURL(attachedFile);
    });
    fileName = attachedFile.name;
    fileMimeType = attachedFile.type;
  }

  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      model,
      system_prompt: systemPrompt,
      file_data: fileData,
      file_name: fileName,
      file_mime_type: fileMimeType,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    appendMessage('meta', ` Error: ${error.detail || 'Request failed'}`);
    return;
  }

  const data = await response.json();
  appendMessage('assistant', data.reply || '(no response)');

  // Clear file after sending
  attachedFile = null;
  fileInputEl.value = '';
  filePreviewEl.innerHTML = '';
  filePreviewEl.classList.remove('active');
});

// Initialize on page load
setSessionId(getOrCreateSessionId());
currentModel = modelSelectEl ? modelSelectEl.value : '';
// On page load/refresh, clear all model conversations
modelConversations = {};
chatEl.innerHTML = '';

// Model change listener - switch conversations per model
if (modelSelectEl) {
  modelSelectEl.addEventListener('change', (e) => {
    const newModel = e.target.value;
    currentModel = newModel;
    loadModelConversation(currentModel);
  });
}

newChatBtn.addEventListener('click', async () => {
  const oldSessionId = activeSessionId;
  const newSessionId = generateSessionId();
  await clearHistory(oldSessionId);
  setSessionId(newSessionId);
  clearCurrentModelConversation();
  messageEl.value = '';
  systemPromptEl.value = '';
});
