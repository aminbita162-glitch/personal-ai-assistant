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

const AUTH_TOKEN_STORAGE_KEY = "personal_ai_auth_token";

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

async function authorizedFetch(url, options = {}) {
    const existingHeaders = options.headers || {};
    const finalOptions = {
        ...options,
        headers: getAuthHeaders(existingHeaders)
    };

    const response = await fetch(url, finalOptions);

    if (response.status === 401) {
        clearAuthToken();

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

function renderReminders(tasks, appointments) {
    if (!remindersList) {
        return;
    }

    const reminderItems = [];

    if (Array.isArray(tasks)) {
        tasks.forEach(task => {
            reminderItems.push(`
                <div class="task-item">
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
            reminderItems.push(`
                <div class="task-item">
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

async function loadReminders() {
    if (!remindersList) {
        return;
    }

    remindersList.innerHTML = `<div class="loading">Loading reminders...</div>`;

    const res = await authorizedFetch("/reminders");
    const data = await res.json();

    if (data.status !== "success") {
        remindersList.innerHTML = `<div class="loading">Could not load reminders.</div>`;
        return;
    }

    renderReminders(data.tasks || [], data.appointments || []);
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

    const res = await fetch(`/smart-ai-browser?message=${encodeURIComponent(message)}`);
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
    refreshTasksButton.addEventListener("click", function () {
        loadTasks();
        loadAppointments();
        loadReminders();
    });
}

if (refreshRemindersButton) {
    refreshRemindersButton.addEventListener("click", loadReminders);
}

loadTasks();
loadAppointments();
loadReminders();
loadAppInfo();