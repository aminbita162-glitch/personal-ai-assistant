const resultBox = document.getElementById("resultBox");
const statusText = document.getElementById("statusText");
const tasksList = document.getElementById("tasksList");
const messageInput = document.getElementById("messageInput");
const dueDateInput = document.getElementById("dueDateInput");
const sendButton = document.getElementById("sendButton");
const refreshTasksButton = document.getElementById("refreshTasksButton");

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

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function renderTasks(tasks) {
    tasksList.innerHTML = tasks.map(task => {
        return `
        <div class="task-item ${task.status === 'done' ? 'task-done' : ''}">
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

async function loadTasks() {
    tasksList.innerHTML = `<div class="loading">Loading tasks...</div>`;

    const res = await fetch("/tasks");
    const data = await res.json();

    if (!data.tasks || !Array.isArray(data.tasks)) {
        tasksList.innerHTML = `<div class="loading">Could not load tasks.</div>`;
        return;
    }

    renderTasks(data.tasks);
}

async function createTaskFromMessage(message, dueDateValue) {
    const createRes = await fetch("/tasks", {
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
    const updateRes = await fetch(`/tasks/${taskId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            due_date: dueDateValue || null
        })
    });

    return await updateRes.json();
}

function renderReplyResult(replyText) {
    resultBox.textContent = replyText;
}

function renderTaskResult(taskData, actionLabel) {
    resultBox.textContent = JSON.stringify({
        status: "success",
        action: actionLabel,
        task: taskData
    }, null, 2);
}

async function sendMessage() {
    const message = messageInput.value.trim();
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
        messageInput.value = "";
        if (dueDateInput) {
            dueDateInput.value = "";
        }
        loadTasks();
        return;
    }

    if (!dueDateValue) {
        resultBox.textContent = JSON.stringify(data, null, 2);
        statusText.textContent = "Done";
        loadTasks();
        return;
    }

    const manualTaskData = await createTaskFromMessage(message, dueDateValue);
    resultBox.textContent = JSON.stringify(manualTaskData, null, 2);
    statusText.textContent = "Done";
    messageInput.value = "";
    if (dueDateInput) {
        dueDateInput.value = "";
    }
    loadTasks();
}

async function updateTask(id, status) {
    await fetch(`/tasks/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status })
    });

    statusText.textContent = "Task updated";
    loadTasks();
}

async function deleteTask(id) {
    if (!confirm("Delete this task?")) return;

    await fetch(`/tasks/${id}`, {
        method: "DELETE"
    });

    statusText.textContent = "Task deleted";
    loadTasks();
}

if (sendButton) {
    sendButton.addEventListener("click", sendMessage);
}

if (refreshTasksButton) {
    refreshTasksButton.addEventListener("click", loadTasks);
}

loadTasks();