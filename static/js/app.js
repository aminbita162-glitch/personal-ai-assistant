const resultBox = document.getElementById("resultBox");
const statusText = document.getElementById("statusText");
const tasksList = document.getElementById("tasksList");
const appointmentsList = document.getElementById("appointmentsList");
const remindersList = document.getElementById("remindersList");
const messageInput = document.getElementById("messageInput");
const dueDateInput = document.getElementById("dueDateInput");
const sendButton = document.getElementById("sendButton");
const refreshTasksButton = document.getElementById("refreshTasksButton");
const refreshRemindersButton = document.getElementById("refreshRemindersButton");

const emailInput = document.getElementById("emailInput");
const passwordInput = document.getElementById("passwordInput");
const signupButton = document.getElementById("signupButton");
const loginButton = document.getElementById("loginButton");
const logoutButton = document.getElementById("logoutButton");
const authStatusText = document.getElementById("authStatusText");
const togglePasswordButton = document.getElementById("togglePasswordButton");

const refreshLocationButton = document.getElementById("refreshLocationButton");
const locationStatusText = document.getElementById("locationStatusText");
const locationLiveText = document.getElementById("locationLiveText");
const locationCountryText = document.getElementById("locationCountryText");
const locationCityText = document.getElementById("locationCityText");
const locationLatitudeText = document.getElementById("locationLatitudeText");
const locationLongitudeText = document.getElementById("locationLongitudeText");

const startVoiceButton = document.getElementById("startVoiceButton");
const stopVoiceButton = document.getElementById("stopVoiceButton");
const voiceStatusText = document.getElementById("voiceStatusText");
const voiceTranscriptBox = document.getElementById("voiceTranscriptBox");

const AUTH_TOKEN_STORAGE_KEY = "personal_ai_auth_token";
const LOCATION_STORAGE_KEY = "personal_ai_live_location_cache";
const AUTO_REMINDER_INTERVAL_MS = 30000;
const REMINDER_LOOKAHEAD_MS = 60 * 1000;
const REMINDER_OVERDUE_GRACE_MS = 5 * 60 * 1000;

let reminderAutoRefreshIntervalId = null;
let isLoadingReminders = false;
let lastReminderSignature = "";
let shownReminderIds = new Set();
let reminderAudioContext = null;
let reminderSoundEnabled = false;
let reminderSoundUnlockListenersInstalled = false;

let mediaRecorder = null;
let mediaStream = null;
let recordedAudioChunks = [];
let isVoiceRecording = false;
let voiceRecordingSupported = false;
let lastRecordedAudioBlob = null;
let lastRecordedAudioUrl = "";
let lastRecordedAudioMimeType = "";

function formatDateForDisplay(value) {
    if (!value) {
        return "No due date";
    }

    try {
        return new Date(value).toLocaleString();
    } catch (error) {
        return value;
    }
}

function formatAppointmentTimeForDisplay(value) {
    if (!value) {
        return "No time";
    }

    try {
        return new Date(value).toLocaleString();
    } catch (error) {
        return value;
    }
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function getAuthToken() {
    try {
        return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || "";
    } catch (error) {
        return "";
    }
}

function setAuthToken(token) {
    try {
        if (token) {
            localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
        }
    } catch (error) {
        console.error("Failed to save auth token:", error);
    }
}

function clearAuthToken() {
    try {
        localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    } catch (error) {
        console.error("Failed to clear auth token:", error);
    }
}

function getAuthHeaders(extraHeaders = {}) {
    const token = getAuthToken();
    const headers = { ...extraHeaders };

    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    return headers;
}

function updateAuthStatus(text) {
    if (authStatusText) {
        authStatusText.textContent = text;
    }
}

function updateLoggedInUiState() {
    if (getAuthToken()) {
        updateAuthStatus("Logged in");
    } else {
        updateAuthStatus("Not logged in");
    }
}

function togglePasswordVisibility() {
    if (!passwordInput || !togglePasswordButton) {
        return;
    }

    const isPasswordHidden = passwordInput.type === "password";

    passwordInput.type = isPasswordHidden ? "text" : "password";
    togglePasswordButton.textContent = isPasswordHidden ? "🙈" : "👁";
    togglePasswordButton.setAttribute(
        "aria-label",
        isPasswordHidden ? "Hide password" : "Show password"
    );
    togglePasswordButton.setAttribute(
        "title",
        isPasswordHidden ? "Hide password" : "Show password"
    );
}

async function authorizedFetch(url, options = {}) {
    const existingHeaders = options.headers || {};
    const finalOptions = {
        ...options,
        headers: getAuthHeaders(existingHeaders)
    };

    const response = await fetch(url, finalOptions);

    if (response.status === 401) {
        clearAuthToken();
        stopReminderAutoRefresh();
        shownReminderIds = new Set();
        updateAuthStatus("Please login again");

        if (statusText) {
            statusText.textContent = "Please login again";
        }
    }

    return response;
}

function renderTasks(tasks) {
    if (!tasksList) {
        return;
    }

    if (!tasks || !Array.isArray(tasks) || tasks.length === 0) {
        tasksList.innerHTML = `<div class="loading">No tasks yet.</div>`;
        return;
    }

    tasksList.innerHTML = tasks.map(task => {
        return `
        <div class="task-item ${task.status === "done" ? "task-done" : ""}">
            <strong>${escapeHtml(task.title)}</strong><br>
            ${escapeHtml(task.description || "No description")}<br>
            Task ID: ${task.id}<br>
            Created at: ${escapeHtml(task.created_at)}<br>
            Due date: ${escapeHtml(formatDateForDisplay(task.due_date))}<br>

            <span class="badge badge-priority">Priority: ${escapeHtml(task.priority)}</span>
            <span class="badge badge-status">Status: ${escapeHtml(task.status)}</span>

            <div class="task-actions">
                <button class="done-btn" onclick="updateTask(${task.id}, 'done')">Mark as Done</button>
                <button class="pending-btn" onclick="updateTask(${task.id}, 'pending')">Mark as Pending</button>
                <button class="delete-btn" onclick="deleteTask(${task.id})">Delete</button>
            </div>
        </div>
        `;
    }).join("");
}

function renderAppointments(appointments) {
    if (!appointmentsList) {
        return;
    }

    if (!appointments || !Array.isArray(appointments) || appointments.length === 0) {
        appointmentsList.innerHTML = `<div class="loading">No appointments yet.</div>`;
        return;
    }

    appointmentsList.innerHTML = appointments.map(appointment => {
        return `
        <div class="task-item">
            <strong>${escapeHtml(appointment.title)}</strong><br>
            ${escapeHtml(appointment.description || "No description")}<br>
            Appointment ID: ${appointment.id}<br>
            Time: ${escapeHtml(formatAppointmentTimeForDisplay(appointment.appointment_time))}<br>
            Location: ${escapeHtml(appointment.location || "No location")}<br>
            Created at: ${escapeHtml(appointment.created_at)}<br>

            <span class="badge badge-status">Status: ${escapeHtml(appointment.status || "scheduled")}</span>
        </div>
        `;
    }).join("");
}

function supportsBrowserNotifications() {
    return typeof window !== "undefined" && "Notification" in window;
}

async function ensureBrowserNotificationPermission() {
    if (!supportsBrowserNotifications()) {
        return "unsupported";
    }

    if (Notification.permission === "granted") {
        return "granted";
    }

    if (Notification.permission === "denied") {
        return "denied";
    }

    try {
        return await Notification.requestPermission();
    } catch (error) {
        console.error("Failed to request notification permission:", error);
        return "error";
    }
}

function showBrowserNotification(message) {
    if (!supportsBrowserNotifications()) {
        return;
    }

    if (Notification.permission !== "granted") {
        return;
    }

    try {
        const notification = new Notification("Reminder", {
            body: message,
            tag: `reminder-${message}`,
            renotify: true
        });

        window.setTimeout(() => {
            try {
                notification.close();
            } catch (error) {
                console.error("Failed to close browser notification:", error);
            }
        }, 5000);
    } catch (error) {
        console.error("Failed to show browser notification:", error);
    }
}

async function unlockReminderSound() {
    try {
        if (!reminderAudioContext) {
            reminderAudioContext = new (window.AudioContext || window.webkitAudioContext)();
        }

        if (reminderAudioContext.state === "suspended") {
            await reminderAudioContext.resume();
        }

        const oscillator = reminderAudioContext.createOscillator();
        const gainNode = reminderAudioContext.createGain();

        oscillator.type = "sine";
        oscillator.frequency.setValueAtTime(440, reminderAudioContext.currentTime);
        gainNode.gain.setValueAtTime(0.0001, reminderAudioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, reminderAudioContext.currentTime + 0.01);
        gainNode.gain.exponentialRampToValueAtTime(0.0001, reminderAudioContext.currentTime + 0.03);

        oscillator.connect(gainNode);
        gainNode.connect(reminderAudioContext.destination);

        oscillator.start(reminderAudioContext.currentTime);
        oscillator.stop(reminderAudioContext.currentTime + 0.03);

        reminderSoundEnabled = true;
    } catch (error) {
        console.error("Failed to unlock reminder sound:", error);
    }
}

function installReminderSoundUnlockListeners() {
    if (reminderSoundUnlockListenersInstalled) {
        return;
    }

    const unlockOnce = async function () {
        await unlockReminderSound();

        if (reminderSoundEnabled) {
            document.removeEventListener("touchstart", unlockOnce);
            document.removeEventListener("touchend", unlockOnce);
            document.removeEventListener("click", unlockOnce);
            document.removeEventListener("keydown", unlockOnce);
        }
    };

    document.addEventListener("touchstart", unlockOnce, { passive: true });
    document.addEventListener("touchend", unlockOnce, { passive: true });
    document.addEventListener("click", unlockOnce);
    document.addEventListener("keydown", unlockOnce);

    reminderSoundUnlockListenersInstalled = true;
}

async function playReminderSound() {
    if (!reminderSoundEnabled) {
        return;
    }

    try {
        if (!reminderAudioContext) {
            reminderAudioContext = new (window.AudioContext || window.webkitAudioContext)();
        }

        if (reminderAudioContext.state === "suspended") {
            await reminderAudioContext.resume();
        }

        const oscillator = reminderAudioContext.createOscillator();
        const gainNode = reminderAudioContext.createGain();

        oscillator.type = "sine";
        oscillator.frequency.setValueAtTime(880, reminderAudioContext.currentTime);
        gainNode.gain.setValueAtTime(0.001, reminderAudioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.12, reminderAudioContext.currentTime + 0.02);
        gainNode.gain.exponentialRampToValueAtTime(0.001, reminderAudioContext.currentTime + 0.28);

        oscillator.connect(gainNode);
        gainNode.connect(reminderAudioContext.destination);

        oscillator.start(reminderAudioContext.currentTime);
        oscillator.stop(reminderAudioContext.currentTime + 0.28);
    } catch (error) {
        console.error("Failed to play reminder sound:", error);
    }
}

async function showNotification(message) {
    await playReminderSound();
    showBrowserNotification(message);

    const existingToast = document.getElementById("reminderToast");
    if (existingToast) {
        existingToast.remove();
    }

    const toast = document.createElement("div");
    toast.id = "reminderToast";
    toast.className = "reminder-toast";
    toast.innerHTML = `
        <div class="reminder-toast-content">
            <div class="reminder-toast-icon">⏰</div>
            <div class="reminder-toast-message">${escapeHtml(message)}</div>
            <button type="button" class="reminder-toast-close" id="reminderToastCloseButton">×</button>
        </div>
    `;

    document.body.appendChild(toast);

    const closeButton = document.getElementById("reminderToastCloseButton");
    if (closeButton) {
        closeButton.addEventListener("click", function () {
            toast.remove();
        });
    }

    window.setTimeout(() => {
        if (toast.parentNode) {
            toast.remove();
        }
    }, 5000);
}

function parseReminderDate(value) {
    if (!value) {
        return null;
    }

    const parsedDate = new Date(value);

    if (Number.isNaN(parsedDate.getTime())) {
        return null;
    }

    return parsedDate;
}

function isReminderTriggerable(dateValue) {
    const dueDate = parseReminderDate(dateValue);

    if (!dueDate) {
        return false;
    }

    const now = Date.now();
    const dueTime = dueDate.getTime();
    const differenceMs = dueTime - now;

    return differenceMs <= REMINDER_LOOKAHEAD_MS && differenceMs >= -REMINDER_OVERDUE_GRACE_MS;
}

function getReminderNotificationMessage(item, typeLabel) {
    const title = item && item.title ? String(item.title) : "Untitled";
    return `${typeLabel}: ${title}`;
}

function renderReminders(tasks, appointments) {
    if (!remindersList) {
        return;
    }

    const reminderItems = [];

    if (Array.isArray(tasks)) {
        tasks.forEach(task => {
            const reminderKey = `task-${task.id}-${task.due_date || "no-date"}`;
            let reminderClassName = "task-item";
            const shouldTriggerReminder =
                task &&
                task.status !== "done" &&
                isReminderTriggerable(task.due_date);

            if (shouldTriggerReminder && !shownReminderIds.has(reminderKey)) {
                showNotification(getReminderNotificationMessage(task, "Task reminder"));
                shownReminderIds.add(reminderKey);
                reminderClassName = "task-item reminder-highlight";
            }

            reminderItems.push(`
                <div class="${reminderClassName}">
                    <strong>Task reminder</strong><br>
                    Title: ${escapeHtml(task.title)}<br>
                    Due date: ${escapeHtml(formatDateForDisplay(task.due_date))}<br>
                    <span class="badge badge-status">Status: ${escapeHtml(task.status || "pending")}</span>
                </div>
            `);
        });
    }

    if (Array.isArray(appointments)) {
        appointments.forEach(appointment => {
            const reminderKey = `appointment-${appointment.id}-${appointment.appointment_time || "no-time"}`;
            let reminderClassName = "task-item";
            const shouldTriggerReminder =
                appointment &&
                (appointment.status || "scheduled") !== "done" &&
                isReminderTriggerable(appointment.appointment_time);

            if (shouldTriggerReminder && !shownReminderIds.has(reminderKey)) {
                showNotification(getReminderNotificationMessage(appointment, "Appointment reminder"));
                shownReminderIds.add(reminderKey);
                reminderClassName = "task-item reminder-highlight";
            }

            reminderItems.push(`
                <div class="${reminderClassName}">
                    <strong>Appointment reminder</strong><br>
                    Title: ${escapeHtml(appointment.title)}<br>
                    Time: ${escapeHtml(formatAppointmentTimeForDisplay(appointment.appointment_time))}<br>
                    <span class="badge badge-status">Status: ${escapeHtml(appointment.status || "scheduled")}</span>
                </div>
            `);
        });
    }

    if (reminderItems.length === 0) {
        remindersList.innerHTML = `<div class="loading">No reminders right now.</div>`;
        return;
    }

    remindersList.innerHTML = reminderItems.join("");
}

function buildReminderSignature(tasks, appointments) {
    return JSON.stringify({
        tasks: Array.isArray(tasks) ? tasks : [],
        appointments: Array.isArray(appointments) ? appointments : []
    });
}

function ensureReminderUiStyle() {
    if (document.getElementById("reminderUiStyle")) {
        return;
    }

    const style = document.createElement("style");
    style.id = "reminderUiStyle";
    style.textContent = `
        .reminder-highlight {
            animation: reminderPulse 1.2s ease-in-out 5;
            box-shadow: 0 0 0 3px rgba(255, 193, 7, 0.35);
            border: 2px solid rgba(255, 193, 7, 0.85);
            background: rgba(255, 248, 225, 0.98);
        }

        .reminder-toast {
            position: fixed;
            top: 20px;
            left: 16px;
            right: 16px;
            z-index: 9999;
            animation: reminderToastSlideDown 0.25s ease-out;
        }

        .reminder-toast-content {
            display: flex;
            align-items: center;
            gap: 12px;
            width: 100%;
            box-sizing: border-box;
            background: #ffffff;
            color: #111827;
            border-radius: 18px;
            padding: 16px 18px;
            box-shadow: 0 12px 35px rgba(0, 0, 0, 0.18);
            border: 1px solid rgba(15, 23, 42, 0.08);
        }

        .reminder-toast-icon {
            font-size: 28px;
            line-height: 1;
            flex: 0 0 auto;
        }

        .reminder-toast-message {
            flex: 1 1 auto;
            min-width: 0;
            font-size: 18px;
            font-weight: 700;
            line-height: 1.35;
            white-space: normal;
            word-break: normal;
            overflow-wrap: anywhere;
        }

        .reminder-toast-close {
            margin-left: auto;
            border: none;
            background: transparent;
            color: #2563eb;
            font-size: 28px;
            line-height: 1;
            font-weight: 700;
            cursor: pointer;
            flex: 0 0 auto;
            padding: 0;
        }

        #voiceTranscriptBox {
            min-height: 56px;
            border: 1px solid rgba(15, 23, 42, 0.12);
            border-radius: 12px;
            padding: 12px;
            background: rgba(248, 250, 252, 0.95);
            color: #111827;
            line-height: 1.5;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .voice-audio-player {
            width: 100%;
            margin-top: 12px;
        }

        @keyframes reminderPulse {
            0% {
                transform: scale(1);
                box-shadow: 0 0 0 0 rgba(255, 193, 7, 0.55);
            }
            50% {
                transform: scale(1.02);
                box-shadow: 0 0 0 10px rgba(255, 193, 7, 0.14);
            }
            100% {
                transform: scale(1);
                box-shadow: 0 0 0 0 rgba(255, 193, 7, 0);
            }
        }

        @keyframes reminderToastSlideDown {
            from {
                opacity: 0;
                transform: translateY(-12px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    `;
    document.head.appendChild(style);
}

function updateLocationStatus(text) {
    if (locationStatusText) {
        locationStatusText.textContent = text;
    }
}

function updateLocationFields(locationData) {
    if (locationLiveText) {
        locationLiveText.textContent = locationData.live || "Unknown";
    }

    if (locationCountryText) {
        locationCountryText.textContent = locationData.country || "Unknown";
    }

    if (locationCityText) {
        locationCityText.textContent = locationData.city || "Unknown";
    }

    if (locationLatitudeText) {
        locationLatitudeText.textContent =
            typeof locationData.latitude === "number"
                ? locationData.latitude.toFixed(6)
                : (locationData.latitude || "—");
    }

    if (locationLongitudeText) {
        locationLongitudeText.textContent =
            typeof locationData.longitude === "number"
                ? locationData.longitude.toFixed(6)
                : (locationData.longitude || "—");
    }
}

function saveLocationCache(locationData) {
    try {
        localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify(locationData));
    } catch (error) {
        console.error("Failed to save location cache:", error);
    }
}

function loadLocationCache() {
    try {
        const raw = localStorage.getItem(LOCATION_STORAGE_KEY);
        if (!raw) {
            return null;
        }

        return JSON.parse(raw);
    } catch (error) {
        console.error("Failed to load location cache:", error);
        return null;
    }
}

function restoreCachedLocation() {
    const cachedLocation = loadLocationCache();
    if (!cachedLocation) {
        return;
    }

    updateLocationFields(cachedLocation);
    updateLocationStatus(cachedLocation.status || "Showing last known location.");
}

async function reverseGeocode(latitude, longitude) {
    const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${encodeURIComponent(latitude)}&lon=${encodeURIComponent(longitude)}`;

    const response = await fetch(url, {
        headers: {
            "Accept": "application/json"
        }
    });

    if (!response.ok) {
        throw new Error("Failed to reverse geocode location");
    }

    const data = await response.json();
    const address = data.address || {};

    const country = address.country || "Unknown";

    const city =
        address.city ||
        address.town ||
        address.village ||
        address.state ||
        address.region ||
        "Unknown";

    return {
        country,
        city,
        live: city !== "Unknown" && country !== "Unknown" ? `${city}, ${country}` : country
    };
}

async function loadLiveLocation() {
    if (!navigator.geolocation) {
        updateLocationStatus("Geolocation is not supported on this device.");
        return;
    }

    updateLocationStatus("Getting live location...");

    navigator.geolocation.getCurrentPosition(
        async function (position) {
            try {
                const latitude = position.coords.latitude;
                const longitude = position.coords.longitude;

                updateLocationStatus("Resolving location details...");

                const resolved = await reverseGeocode(latitude, longitude);

                const locationData = {
                    status: "Live location loaded.",
                    live: resolved.live,
                    country: resolved.country,
                    city: resolved.city,
                    latitude,
                    longitude
                };

                updateLocationFields(locationData);
                updateLocationStatus(locationData.status);
                saveLocationCache(locationData);
            } catch (error) {
                console.error("Failed to resolve live location:", error);

                const fallbackLocation = {
                    status: "Coordinates loaded, but place name could not be resolved.",
                    live: "Live coordinates",
                    country: "Unknown",
                    city: "Unknown",
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                };

                updateLocationFields(fallbackLocation);
                updateLocationStatus(fallbackLocation.status);
                saveLocationCache(fallbackLocation);
            }
        },
        function (error) {
            console.error("Failed to get live location:", error);

            if (error.code === 1) {
                updateLocationStatus("Location permission was denied.");
            } else if (error.code === 2) {
                updateLocationStatus("Location is unavailable right now.");
            } else if (error.code === 3) {
                updateLocationStatus("Location request timed out.");
            } else {
                updateLocationStatus("Could not get live location.");
            }
        },
        {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 0
        }
    );
}

function setVoiceStatus(text) {
    if (voiceStatusText) {
        voiceStatusText.textContent = text;
    }
}

function clearLastRecordedAudioUrl() {
    if (lastRecordedAudioUrl) {
        try {
            URL.revokeObjectURL(lastRecordedAudioUrl);
        } catch (error) {
            console.error("Failed to revoke audio URL:", error);
        }
        lastRecordedAudioUrl = "";
    }
}

function setVoiceTranscriptContent(content) {
    if (!voiceTranscriptBox) {
        return;
    }

    voiceTranscriptBox.innerHTML = "";
    if (typeof content === "string") {
        voiceTranscriptBox.textContent = content;
        return;
    }

    if (content) {
        voiceTranscriptBox.appendChild(content);
    }
}

function setVoiceTranscript(text) {
    setVoiceTranscriptContent(text || "No voice recording yet.");
}

function supportsRealVoiceRecording() {
    return (
        typeof window !== "undefined" &&
        !!navigator.mediaDevices &&
        typeof navigator.mediaDevices.getUserMedia === "function" &&
        typeof window.MediaRecorder !== "undefined"
    );
}

function getPreferredAudioMimeType() {
    const mimeTypes = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/mp4",
        "audio/mpeg"
    ];

    for (let i = 0; i < mimeTypes.length; i += 1) {
        const mimeType = mimeTypes[i];
        try {
            if (MediaRecorder.isTypeSupported(mimeType)) {
                return mimeType;
            }
        } catch (error) {
            console.error("Failed to test mime type:", error);
        }
    }

    return "";
}

function stopVoiceStreamTracks() {
    if (!mediaStream) {
        return;
    }

    const tracks = mediaStream.getTracks();
    tracks.forEach(track => {
        try {
            track.stop();
        } catch (error) {
            console.error("Failed to stop media track:", error);
        }
    });

    mediaStream = null;
}

function renderRecordedAudioPreview() {
    if (!lastRecordedAudioBlob || !lastRecordedAudioUrl) {
        setVoiceTranscript("No voice recording yet.");
        return;
    }

    const wrapper = document.createElement("div");

    const text = document.createElement("div");
    text.textContent = `Voice recorded successfully. Size: ${Math.round(lastRecordedAudioBlob.size / 1024)} KB`;
    wrapper.appendChild(text);

    const audio = document.createElement("audio");
    audio.className = "voice-audio-player";
    audio.controls = true;
    audio.src = lastRecordedAudioUrl;
    wrapper.appendChild(audio);

    setVoiceTranscriptContent(wrapper);
}

function updateVoiceButtonsState() {
    if (startVoiceButton) {
        startVoiceButton.disabled = isVoiceRecording;
    }

    if (stopVoiceButton) {
        stopVoiceButton.disabled = !isVoiceRecording;
    }
}

function initVoiceRecording() {
    voiceRecordingSupported = supportsRealVoiceRecording();

    if (!voiceRecordingSupported) {
        setVoiceStatus("Microphone recording is not supported on this device.");
        setVoiceTranscript("No voice recording yet.");
        updateVoiceButtonsState();
        return;
    }

    setVoiceStatus("Microphone is ready.");
    setVoiceTranscript("No voice recording yet.");
    updateVoiceButtonsState();
}

async function startVoiceInput() {
    if (!voiceRecordingSupported) {
        setVoiceStatus("Microphone recording is not supported on this device.");
        return;
    }

    if (isVoiceRecording) {
        return;
    }

    try {
        clearLastRecordedAudioUrl();
        lastRecordedAudioBlob = null;
        lastRecordedAudioMimeType = "";
        recordedAudioChunks = [];

        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: true
        });

        const preferredMimeType = getPreferredAudioMimeType();
        const mediaRecorderOptions = preferredMimeType ? { mimeType: preferredMimeType } : {};

        mediaRecorder = new MediaRecorder(mediaStream, mediaRecorderOptions);
        lastRecordedAudioMimeType = preferredMimeType || mediaRecorder.mimeType || "audio/webm";

        mediaRecorder.onstart = function () {
            isVoiceRecording = true;
            setVoiceStatus("Recording voice...");
            setVoiceTranscript("Recording in progress...");
            updateVoiceButtonsState();
        };

        mediaRecorder.ondataavailable = function (event) {
            if (event.data && event.data.size > 0) {
                recordedAudioChunks.push(event.data);
            }
        };

        mediaRecorder.onerror = function (event) {
            console.error("MediaRecorder error:", event);
            isVoiceRecording = false;
            setVoiceStatus("Voice recording failed.");
            updateVoiceButtonsState();
            stopVoiceStreamTracks();
        };

        mediaRecorder.onstop = function () {
            isVoiceRecording = false;

            try {
                const audioBlob = new Blob(recordedAudioChunks, {
                    type: lastRecordedAudioMimeType || "audio/webm"
                });

                if (audioBlob.size > 0) {
                    lastRecordedAudioBlob = audioBlob;
                    lastRecordedAudioUrl = URL.createObjectURL(audioBlob);
                    renderRecordedAudioPreview();
                    setVoiceStatus("Voice recording completed.");

                    sendAudioToServer(audioBlob);
                } else {
                    lastRecordedAudioBlob = null;
                    setVoiceTranscript("No audio was captured.");
                    setVoiceStatus("Voice recording completed, but no audio was captured.");
                }
            } catch (error) {
                console.error("Failed to finalize voice recording:", error);
                setVoiceStatus("Could not process recorded audio.");
                setVoiceTranscript("Recorded audio could not be processed.");
            }

            recordedAudioChunks = [];
            updateVoiceButtonsState();
            stopVoiceStreamTracks();
        };

        mediaRecorder.start();
    } catch (error) {
        console.error("Failed to start microphone recording:", error);

        isVoiceRecording = false;
        updateVoiceButtonsState();
        stopVoiceStreamTracks();

        if (error && error.name === "NotAllowedError") {
            setVoiceStatus("Microphone permission was denied.");
        } else if (error && error.name === "NotFoundError") {
            setVoiceStatus("No microphone was found on this device.");
        } else if (error && error.name === "NotReadableError") {
            setVoiceStatus("Microphone is already in use or not readable.");
        } else {
            setVoiceStatus("Could not start microphone recording.");
        }

        setVoiceTranscript("No voice recording yet.");
    }
}

function stopVoiceInput() {
    if (!mediaRecorder || !isVoiceRecording) {
        return;
    }

    try {
        mediaRecorder.stop();
        setVoiceStatus("Stopping voice recording...");
    } catch (error) {
        console.error("Failed to stop microphone recording:", error);
        setVoiceStatus("Could not stop voice recording.");
    }
}

async function sendAudioToServer(audioBlob) {
    try {
        if (!audioBlob || audioBlob.size === 0) {
            setVoiceStatus("No audio captured");
            return;
        }

        const formData = new FormData();
        formData.append("audio", audioBlob, "voice.webm");

        setVoiceStatus("Processing voice...");

        const response = await authorizedFetch("/transcribe-voice", {
            method: "POST",
            body: formData
        });

        let data;
        try {
            data = await response.json();
        } catch (e) {
            setVoiceStatus("Invalid server response");
            return;
        }

        if (!response.ok) {
            setVoiceStatus("Server error during voice processing");
            return;
        }

        if (!data || data.status !== "success") {
            setVoiceStatus((data && data.message) || "Voice processing failed");
            return;
        }

        const transcribedText = String(data.text || "").trim();

        if (!transcribedText) {
            setVoiceStatus("No speech detected");
            return;
        }

        if (messageInput) {
            messageInput.value = transcribedText;
            messageInput.focus();
        }

        setVoiceTranscript(transcribedText);
        setVoiceStatus("Voice converted to text");
    } catch (error) {
        console.error("Failed to convert voice to text:", error);
        setVoiceStatus("Voice conversion failed");
    }
}

function startReminderAutoRefresh() {
    if (!getAuthToken()) {
        return;
    }

    if (reminderAutoRefreshIntervalId) {
        return;
    }

    reminderAutoRefreshIntervalId = window.setInterval(() => {
        loadReminders({ silent: true });
    }, AUTO_REMINDER_INTERVAL_MS);
}

function stopReminderAutoRefresh() {
    if (reminderAutoRefreshIntervalId) {
        window.clearInterval(reminderAutoRefreshIntervalId);
        reminderAutoRefreshIntervalId = null;
    }
}

async function loadTasks() {
    if (!tasksList) {
        return;
    }

    tasksList.innerHTML = `<div class="loading">Loading tasks...</div>`;

    const res = await authorizedFetch("/tasks");
    const data = await res.json();

    if (!data.tasks || !Array.isArray(data.tasks)) {
        tasksList.innerHTML = `<div class="loading">Could not load tasks.</div>`;
        return;
    }

    renderTasks(data.tasks);
}

async function loadAppointments() {
    if (!appointmentsList) {
        return;
    }

    appointmentsList.innerHTML = `<div class="loading">Loading appointments...</div>`;

    const res = await authorizedFetch("/appointments");
    const data = await res.json();

    if (!data.appointments || !Array.isArray(data.appointments)) {
        appointmentsList.innerHTML = `<div class="loading">Could not load appointments.</div>`;
        return;
    }

    renderAppointments(data.appointments);
}

async function loadReminders(options = {}) {
    const { silent = false } = options;

    if (!remindersList) {
        return;
    }

    if (!getAuthToken()) {
        remindersList.innerHTML = `<div class="loading">No reminders right now.</div>`;
        return;
    }

    if (isLoadingReminders) {
        return;
    }

    isLoadingReminders = true;

    if (!silent) {
        remindersList.innerHTML = `<div class="loading">Loading reminders...</div>`;
    }

    try {
        const res = await authorizedFetch("/reminders");
        const data = await res.json();

        if (data.status !== "success") {
            remindersList.innerHTML = `<div class="loading">Could not load reminders.</div>`;
            return;
        }

        const tasks = data.tasks || [];
        const appointments = data.appointments || [];
        const nextSignature = buildReminderSignature(tasks, appointments);

        if (nextSignature === lastReminderSignature && silent) {
            return;
        }

        lastReminderSignature = nextSignature;
        renderReminders(tasks, appointments);
    } catch (error) {
        console.error("Failed to load reminders:", error);
        remindersList.innerHTML = `<div class="loading">Could not load reminders.</div>`;
    } finally {
        isLoadingReminders = false;
    }
}

async function loadAppInfo() {
    try {
        const res = await fetch("/app-info");
        const data = await res.json();

        const aboutBoxes = document.querySelectorAll(".task-item");
        const aboutBox = aboutBoxes.length > 0 ? aboutBoxes[aboutBoxes.length - 1] : null;

        if (!aboutBox) {
            return;
        }

        aboutBox.innerHTML = `
            <strong>App Name:</strong> ${escapeHtml(data.name || "Personal AI Assistant")}<br>
            <strong>Version:</strong> ${escapeHtml(data.version || "1.0.0")}<br>
            <strong>Author:</strong> ${escapeHtml(data.author || "Amin Azimi")}<br>
            <strong>Description:</strong> ${escapeHtml(data.description || "A smart productivity assistant.")}
        `;
    } catch (error) {
        console.error("Failed to load app info:", error);
    }
}

async function signup() {
    const email = emailInput ? emailInput.value.trim() : "";
    const password = passwordInput ? passwordInput.value.trim() : "";

    if (!email || !password) {
        updateAuthStatus("Email and password required");
        return;
    }

    updateAuthStatus("Signing up...");

    try {
        const res = await fetch("/signup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json();

        if (data.status === "success" && data.user && data.user.auth_token) {
            setAuthToken(data.user.auth_token);
            updateAuthStatus("Signup successful and logged in");
            startReminderAutoRefresh();
            loadTasks();
            loadAppointments();
            loadReminders();
            return;
        }

        updateAuthStatus(data.message || "Signup failed");
    } catch (error) {
        updateAuthStatus("Signup failed");
        console.error("Signup failed:", error);
    }
}

async function login() {
    const email = emailInput ? emailInput.value.trim() : "";
    const password = passwordInput ? passwordInput.value.trim() : "";

    if (!email || !password) {
        updateAuthStatus("Email and password required");
        return;
    }

    updateAuthStatus("Logging in...");

    try {
        const res = await fetch("/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json();

        if (data.status === "success" && data.user && data.user.auth_token) {
            setAuthToken(data.user.auth_token);
            updateAuthStatus("Logged in");
            startReminderAutoRefresh();
            loadTasks();
            loadAppointments();
            loadReminders();
            return;
        }

        updateAuthStatus(data.message || "Login failed");
    } catch (error) {
        updateAuthStatus("Login failed");
        console.error("Login failed:", error);
    }
}

async function logout() {
    try {
        await authorizedFetch("/logout", {
            method: "POST"
        });
    } catch (error) {
        console.error("Logout request failed:", error);
    }

    clearAuthToken();
    stopReminderAutoRefresh();
    lastReminderSignature = "";
    shownReminderIds = new Set();
    updateAuthStatus("Logged out");

    if (tasksList) {
        tasksList.innerHTML = `<div class="loading">No tasks yet.</div>`;
    }

    if (appointmentsList) {
        appointmentsList.innerHTML = `<div class="loading">No appointments yet.</div>`;
    }

    if (remindersList) {
        remindersList.innerHTML = `<div class="loading">No reminders right now.</div>`;
    }
}

async function createTaskFromMessage(message, dueDateValue) {
    const createRes = await authorizedFetch("/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            title: message,
            due_date: dueDateValue || null
        })
    });

    return await createRes.json();
}

async function updateTaskDueDate(taskId, dueDateValue) {
    const updateRes = await authorizedFetch(`/tasks/${taskId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            due_date: dueDateValue || null
        })
    });

    return await updateRes.json();
}

function renderReplyResult(replyText) {
    if (!resultBox) {
        return;
    }

    resultBox.textContent = replyText;
}

function renderTaskResult(taskData, actionLabel) {
    if (!resultBox) {
        return;
    }

    resultBox.textContent = JSON.stringify({
        status: "success",
        action: actionLabel,
        task: taskData
    }, null, 2);
}

async function sendMessage() {
    const message = messageInput ? messageInput.value.trim() : "";
    const dueDateValue = dueDateInput ? dueDateInput.value : "";

    if (!message) {
        statusText.textContent = "Please enter a message";
        return;
    }

    statusText.textContent = "Sending...";

    await unlockReminderSound();
    await ensureBrowserNotificationPermission();

    const res = await authorizedFetch(`/smart-ai-browser?message=${encodeURIComponent(message)}`);
    const data = await res.json();

    if (data.action === "reply") {
        renderReplyResult(data.reply || "No reply");
        statusText.textContent = "Done";
        return;
    }

    if (data.action === "task" && data.task) {
        let finalTask = data.task;

        if (dueDateValue) {
            const updateData = await updateTaskDueDate(data.task.id, dueDateValue);
            if (updateData.status === "success" && updateData.task) {
                finalTask = updateData.task;
            }
        }

        renderTaskResult(finalTask, "task");
        statusText.textContent = "Done";

        if (messageInput) {
            messageInput.value = "";
        }

        if (dueDateInput) {
            dueDateInput.value = "";
        }

        loadTasks();
        loadAppointments();
        loadReminders();
        return;
    }

    if (!dueDateValue) {
        if (resultBox) {
            resultBox.textContent = JSON.stringify(data, null, 2);
        }

        statusText.textContent = "Done";
        loadTasks();
        loadAppointments();
        loadReminders();
        return;
    }

    const manualTaskData = await createTaskFromMessage(message, dueDateValue);

    if (resultBox) {
        resultBox.textContent = JSON.stringify(manualTaskData, null, 2);
    }

    statusText.textContent = "Done";

    if (messageInput) {
        messageInput.value = "";
    }

    if (dueDateInput) {
        dueDateInput.value = "";
    }

    loadTasks();
    loadAppointments();
    loadReminders();
}

async function updateTask(id, status) {
    await unlockReminderSound();
    await ensureBrowserNotificationPermission();

    await authorizedFetch(`/tasks/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status })
    });

    statusText.textContent = "Task updated";
    loadTasks();
    loadReminders();
}

async function deleteTask(id) {
    if (!confirm("Delete this task?")) {
        return;
    }

    await unlockReminderSound();
    await ensureBrowserNotificationPermission();

    await authorizedFetch(`/tasks/${id}`, {
        method: "DELETE"
    });

    statusText.textContent = "Task deleted";
    loadTasks();
    loadReminders();
}

if (sendButton) {
    sendButton.addEventListener("click", sendMessage);
}

if (refreshTasksButton) {
    refreshTasksButton.addEventListener("click", async function () {
        await unlockReminderSound();
        await ensureBrowserNotificationPermission();
        loadTasks();
        loadAppointments();
        loadReminders();
    });
}

if (refreshRemindersButton) {
    refreshRemindersButton.addEventListener("click", async function () {
        await unlockReminderSound();
        await ensureBrowserNotificationPermission();
        loadReminders();
    });
}

if (refreshLocationButton) {
    refreshLocationButton.addEventListener("click", async function () {
        await unlockReminderSound();
        loadLiveLocation();
    });
}

if (startVoiceButton) {
    startVoiceButton.addEventListener("click", async function () {
        await unlockReminderSound();
        startVoiceInput();
    });
}

if (stopVoiceButton) {
    stopVoiceButton.addEventListener("click", async function () {
        await unlockReminderSound();
        stopVoiceInput();
    });
}

if (togglePasswordButton) {
    togglePasswordButton.addEventListener("click", togglePasswordVisibility);
}

if (signupButton) {
    signupButton.addEventListener("click", async function () {
        await unlockReminderSound();
        await ensureBrowserNotificationPermission();
        signup();
    });
}

if (loginButton) {
    loginButton.addEventListener("click", async function () {
        await unlockReminderSound();
        await ensureBrowserNotificationPermission();
        login();
    });
}

if (logoutButton) {
    logoutButton.addEventListener("click", async function () {
        await unlockReminderSound();
        await ensureBrowserNotificationPermission();
        logout();
    });
}

document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
        stopReminderAutoRefresh();
        return;
    }

    if (getAuthToken()) {
        loadReminders({ silent: true });
        startReminderAutoRefresh();
    }
});

ensureReminderUiStyle();
installReminderSoundUnlockListeners();
updateLoggedInUiState();
restoreCachedLocation();
initVoiceRecording();
updateVoiceButtonsState();

if (getAuthToken()) {
    startReminderAutoRefresh();
}

loadTasks();
loadAppointments();
loadReminders();
loadAppInfo();