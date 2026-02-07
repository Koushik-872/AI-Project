// ── DOM refs ───────────────────────────────────────────────────────────────
const startChatBtn = document.getElementById("startChatBtn");
const closeChat    = document.getElementById("closeChat");
const chatSection  = document.getElementById("chatSection");
const chatBody     = document.getElementById("chatBody");
const textInput    = document.getElementById("textInput");
const sendBtn      = document.getElementById("sendBtn");
const micBtn       = document.getElementById("micBtn");
const micStatus    = document.getElementById("micStatus");
const clearBtn     = document.getElementById("clearBtn");

// ── API Configuration ──────────────────────────────────────────────────────
// Change this to your Flask server URL when deploying
const API_BASE_URL = "https://mern-movie-o9y1.onrender.com";

// For production, use:
// const API_BASE_URL = "https://your-server.com";

// ── State ──────────────────────────────────────────────────────────────────
let waitingFor  = null;     // "note" | "rps" | null
let recognition = null;     // current SpeechRecognition instance
let loopActive  = false;    // should the loop keep going?
let locked      = false;    // TRUE = ignore onend/onerror (we stopped it on purpose)
let processing  = false;    // TRUE = fetching/speaking, don't touch mic
let messageCount = 0;       // Track number of messages

// ── Typing simulation for longer responses ────────────────────────────────
function typeMessage(element, text, speed = 30) {
    let i = 0;
    element.textContent = "";
    const interval = setInterval(() => {
        if (i < text.length) {
            element.textContent += text.charAt(i);
            i++;
            chatBody.scrollTop = chatBody.scrollHeight;
        } else {
            clearInterval(interval);
        }
    }, speed);
}

// ── Open chat & START the voice loop ───────────────────────────────────────
startChatBtn.addEventListener("click", () => {
    chatSection.classList.add("open");
    loopActive = true;
    micBtn.classList.add("active");
    micBtn.textContent = "🔇";

    if (chatBody.children.length === 0) {
        const welcome = "Hi! I am WALL-E, your AI assistant. You can say what can you do to see what I can help with.";
        addMessage("bot", welcome);
        speakText(welcome, () => startListenLoop());
    } else if (!processing) {
        startListenLoop();
    }
});

// ── Close chat → kill everything ───────────────────────────────────────────
closeChat.addEventListener("click", () => {
    chatSection.classList.remove("open");
    killLoop();
});

// ── Mic button = MUTE / RESUME ─────────────────────────────────────────────
micBtn.addEventListener("click", () => {
    if (loopActive) {
        killLoop();
        micStatus.textContent = "Tap 🎤 to resume";
    } else {
        loopActive = true;
        micBtn.classList.add("active");
        micBtn.textContent = "🔇";
        startListenLoop();
    }
});

// ── Clear chat button ──────────────────────────────────────────────────────
if (clearBtn) {
    clearBtn.addEventListener("click", () => {
        if (confirm("Clear all chat history?")) {
            chatBody.innerHTML = "";
            messageCount = 0;
            addMessage("bot", "Chat cleared! How can I help you?");
        }
    });
}

// ── Add a message bubble ───────────────────────────────────────────────────
function addMessage(role, text, animated = false) {
    const div = document.createElement("div");
    div.className = "message " + role;
    
    if (animated && role === "bot") {
        typeMessage(div, text);
    } else {
        div.textContent = text;
    }
    
    chatBody.appendChild(div);
    chatBody.scrollTop = chatBody.scrollHeight;
    messageCount++;
    return div;
}

// ── Typing indicator ───────────────────────────────────────────────────────
function showTyping() {
    const div = document.createElement("div");
    div.className = "message bot typing";
    div.id = "typingIndicator";
    div.innerHTML = '<div class="dots"><span></span><span></span><span></span></div>';
    chatBody.appendChild(div);
    chatBody.scrollTop = chatBody.scrollHeight;
}

function hideTyping() {
    const el = document.getElementById("typingIndicator");
    if (el) el.remove();
}

// ── Text-to-Speech with better error handling ──────────────────────────────
function speakText(text, onDone) {
    if (!window.speechSynthesis) { 
        if (onDone) onDone(); 
        return; 
    }

    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    // Remove emojis and clean text (improved emoji regex)
    const clean = text
        .replace(/[\u{1F600}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F900}-\u{1F9FF}\u{2702}-\u{27B0}\u{FE00}-\u{FE0F}\u{200D}]/gu, "")
        .replace(/[•○✓✅⚠️🚀🔇🎤🎙️🔊🧠🔍🌡️🎮😂🧠💪🎉❌]/g, "")
        .trim();

    if (!clean) { 
        if (onDone) onDone(); 
        return; 
    }

    // Split long text into chunks (for better pronunciation)
    const chunks = clean.match(/.{1,200}(?:\s|$)/g) || [clean];
    let currentChunk = 0;

    function speakChunk() {
        if (currentChunk >= chunks.length) {
            if (onDone) onDone();
            return;
        }

        const utt = new SpeechSynthesisUtterance(chunks[currentChunk]);
        utt.rate = 1.05;
        utt.pitch = 1;
        utt.lang = "en-IN";
        
        utt.onend = () => {
            currentChunk++;
            speakChunk();
        };
        
        utt.onerror = (e) => {
            console.error("Speech error:", e);
            currentChunk++;
            speakChunk();
        };

        window.speechSynthesis.speak(utt);
    }

    speakChunk();
}

// ── Safely destroy the current recognition instance ───────────────────────
function destroyRecognition() {
    locked = true;
    if (recognition) {
        recognition.onresult = null;
        recognition.onend    = null;
        recognition.onerror  = null;
        try { recognition.stop(); } catch(e) {}
        recognition = null;
    }
    locked = false;
}

// ── Start listening with improved error handling ──────────────────────────
function startListenLoop() {
    if (processing || !loopActive) return;
    destroyRecognition();

    if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
        addMessage("bot", "⚠️ Browser doesn't support voice recognition. Use Chrome or Edge, or type your message below.");
        return;
    }

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SR();
    recognition.lang = "en-IN";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    // ── GOT SPEECH ─────────────────────────────────────────────────────────
    recognition.onresult = (e) => {
        const transcript = e.results[0][0].transcript;
        const confidence = e.results[0][0].confidence;
        
        console.log(`Recognized: "${transcript}" (confidence: ${confidence})`);
        
        destroyRecognition();
        setStatus("🤖 Thinking...", false);
        sendToBot(transcript);
    };

    // ── MIC STOPPED ────────────────────────────────────────────────────────
    recognition.onend = () => {
        if (locked) return;
        if (!loopActive || processing) return;
        
        // Restart listening after a short delay
        setTimeout(() => {
            if (loopActive && !processing) {
                startListenLoop();
            }
        }, 500);
    };

    // ── MIC ERROR with detailed handling ───────────────────────────────────
    recognition.onerror = (e) => {
        if (locked) return;
        
        console.error("Speech recognition error:", e.error);
        
        // Handle different error types
        switch(e.error) {
            case "no-speech":
                // Just restart, user might speak again
                setTimeout(() => {
                    if (loopActive && !processing) startListenLoop();
                }, 600);
                break;
                
            case "aborted":
                // Restart if still active
                setTimeout(() => {
                    if (loopActive && !processing) startListenLoop();
                }, 600);
                break;
                
            case "audio-capture":
                addMessage("bot", "⚠️ No microphone found. Please check your device settings.");
                killLoop();
                break;
                
            case "not-allowed":
                addMessage("bot", "⚠️ Microphone access denied. Please allow microphone permission in your browser.");
                killLoop();
                break;
                
            case "network":
                addMessage("bot", "⚠️ Network error. Please check your internet connection.");
                setTimeout(() => {
                    if (loopActive && !processing) startListenLoop();
                }, 2000);
                break;
                
            default:
                addMessage("bot", `⚠️ Microphone error: ${e.error}. Trying to restart...`);
                setTimeout(() => {
                    if (loopActive && !processing) startListenLoop();
                }, 1000);
        }
    };

    // Start recognition
    try {
        recognition.start();
        setStatus("🎙️ Listening...", true);
    } catch (e) {
        console.error("Failed to start recognition:", e);
        setTimeout(() => {
            if (loopActive && !processing) startListenLoop();
        }, 1000);
    }
}

// ── Kill the loop completely ───────────────────────────────────────────────
function killLoop() {
    loopActive  = false;
    processing  = false;
    destroyRecognition();
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    micBtn.classList.remove("active");
    micBtn.textContent = "🎤";
    micStatus.textContent = "";
    micStatus.classList.remove("listening");
}

// ── Helper: update status text ─────────────────────────────────────────────
function setStatus(text, isListening) {
    micStatus.textContent = text;
    if (isListening) {
        micStatus.classList.add("listening");
    } else {
        micStatus.classList.remove("listening");
    }
}

// ── Send to Flask with improved error handling ────────────────────────────
async function sendToBot(userMessage) {
    if (!userMessage.trim()) {
        if (loopActive) startListenLoop();
        return;
    }

    processing = true;
    addMessage("user", userMessage);
    showTyping();

    try {
        let endpoint = `${API_BASE_URL}/api/chat`;
        let body = { message: userMessage };

        // Handle special states
        if (waitingFor === "note") {
            endpoint = `${API_BASE_URL}/api/save_note`;
            body = { note: userMessage };
            waitingFor = null;
        } else if (waitingFor === "rps") {
            endpoint = `${API_BASE_URL}/api/rps`;
            body = { choice: userMessage };
            waitingFor = null;
        }

        const res = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });

        if (!res.ok) {
            throw new Error(`Server error: ${res.status}`);
        }

        const data = await res.json();
        hideTyping();

        // Handle URL opening
        if (data.open_url) {
            window.open(data.open_url, "_blank");
        }

        // Handle state changes
        if (data.action === "waiting_note") waitingFor = "note";
        if (data.action === "waiting_rps") waitingFor = "rps";

        // Add bot response with animation for longer messages
        const shouldAnimate = data.reply.length > 100;
        addMessage("bot", data.reply, shouldAnimate);

        // Check for exit commands
        const exitWords = ["exit", "bye", "goodbye", "see you", "quit"];
        if (exitWords.some(w => userMessage.toLowerCase().includes(w))) {
            processing = false;
            killLoop();
            return;
        }

        // Speak response and restart listening
        setStatus("🔊 Speaking...", false);
        speakText(data.reply, () => {
            processing = false;
            if (loopActive) {
                // Wait a bit after speaking before restarting mic
                setTimeout(() => {
                    if (loopActive && !processing) {
                        startListenLoop();
                    }
                }, 800);
            }
        });

    } catch (err) {
        hideTyping();
        console.error("Error communicating with server:", err);
        
        addMessage("bot", "⚠️ Oops! I had trouble connecting to my brain. Please check if the server is running on http://localhost:5000 and try again!");
        
        processing = false;
        if (loopActive) {
            setTimeout(() => {
                startListenLoop();
            }, 2000);
        }
    }
}

// ── Text input (type + Enter or click send) ───────────────────────────────
sendBtn.addEventListener("click", () => {
    const val = textInput.value.trim();
    textInput.value = "";
    if (val) {
        // Pause voice if active
        const wasActive = loopActive;
        if (wasActive) killLoop();
        
        sendToBot(val);
        
        // Resume voice after response if it was active
        if (wasActive) {
            setTimeout(() => {
                loopActive = true;
                micBtn.classList.add("active");
                micBtn.textContent = "🔇";
            }, 100);
        }
    }
});

textInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        const val = textInput.value.trim();
        textInput.value = "";
        if (val) {
            const wasActive = loopActive;
            if (wasActive) killLoop();
            
            sendToBot(val);
            
            if (wasActive) {
                setTimeout(() => {
                    loopActive = true;
                    micBtn.classList.add("active");
                    micBtn.textContent = "🔇";
                }, 100);
            }
        }
    }
});

// ── Auto-scroll chat ───────────────────────────────────────────────────────
const observer = new MutationObserver(() => {
    chatBody.scrollTop = chatBody.scrollHeight;
});

observer.observe(chatBody, { childList: true, subtree: true });

// ── Check browser compatibility ────────────────────────────────────────────
window.addEventListener("load", () => {
    const hasWebSpeech = "webkitSpeechRecognition" in window || "SpeechRecognition" in window;
    const hasSpeechSynthesis = "speechSynthesis" in window;
    
    if (!hasWebSpeech) {
        console.warn("⚠️ Speech recognition not supported in this browser");
    }
    if (!hasSpeechSynthesis) {
        console.warn("⚠️ Speech synthesis not supported in this browser");
    }
    
    console.log("🤖 WALL-E Frontend initialized successfully!");
    console.log(`📡 Backend: ${API_BASE_URL}`);
});

// ── Prevent accidental page closure ───────────────────────────────────────
window.addEventListener("beforeunload", (e) => {
    if (messageCount > 3) {
        e.preventDefault();
        e.returnValue = "";
    }
});

// ── Connection health check (optional - uncomment to enable) ──────────────
/*
async function checkBackendHealth() {
    try {
        const res = await fetch(`${API_BASE_URL}/`, { method: 'GET', timeout: 5000 });
        if (res.ok) {
            const data = await res.json();
            console.log("✅ Backend healthy:", data);
            return true;
        }
    } catch (err) {
        console.warn("⚠️ Backend unreachable:", err.message);
        return false;
    }
}

// Check backend when page loads
window.addEventListener("load", () => {
    checkBackendHealth();
});
*/