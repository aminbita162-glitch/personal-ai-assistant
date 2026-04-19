const resultBox = document.getElementById("resultBox");
const statusText = document.getElementById("statusText");
const tasksList = document.getElementById("tasksList");
const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const refreshTasksButton = document.getElementById("refreshTasksButton");

function renderTasks(tasks) {
    tasksList.innerHTML = tasks.map(task => {
        return `
        <div class="task-item ${task.status === 'done' ? 'task-done' : ''}">
            <strong>${task.title}</strong><br>
            ${task.description || "No description"}<br>
            Task ID: ${task.id}<br>
            Created at: ${task.created_at}<br>

            <span class="badge badge-priority">Priority: ${task.priority}</span>
            <span class="badge badge-status">Status: ${task.status}</span>

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
    renderTasks(data.tasks);
}

async function sendMessage() {
    const message = messageInput.value;
    statusText.textContent = "Sending...";

    const res = await fetch(`/smart-ai-browser?message=${encodeURIComponent(message)}`);
    const data = await res.json();

    resultBox.textContent = JSON.stringify(data, null, 2);
    statusText.textContent = "Done";

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