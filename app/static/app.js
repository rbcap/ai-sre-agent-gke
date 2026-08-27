console.log("AI SRE Agent JS loading...");


// ============================================================
// HELPERS
// ============================================================

function el(id) {
    return document.getElementById(id);
}


function setText(id, value) {
    const node = el(id);

    if (node) {
        node.textContent = value;
    }
}


function escapeHtml(value) {
    const div = document.createElement("div");

    div.textContent =
        value === null || value === undefined
            ? ""
            : String(value);

    return div.innerHTML;
}


// ============================================================
// AUTH HANDLING
// ============================================================

function handleUnauthorized(response) {
    if (response.status === 401) {
        window.location.href = "/login";
        return true;
    }

    return false;
}


// ============================================================
// NAVIGATION
// ============================================================

function showSection(name) {

    document
        .querySelectorAll(".page-section")
        .forEach(section => {
            section.classList.remove("active");
        });


    document
        .querySelectorAll(".nav-item")
        .forEach(button => {
            button.classList.remove("active");
        });


    const target = el(`section-${name}`);

    if (target) {
        target.classList.add("active");
    }


    const nav = document.querySelector(
        `.nav-item[data-section="${name}"]`
    );

    if (nav) {
        nav.classList.add("active");
    }
}


// ============================================================
// HEALTH
// ============================================================

function setStatus(id, text, state) {

    const node = el(id);

    if (!node) {
        console.warn("Missing status element:", id);
        return;
    }


    node.textContent = text;

    node.className = `status ${state}`;
}


async function checkService(url, elementId) {

    setStatus(
        elementId,
        "Checking...",
        "checking"
    );


    try {

        console.log("Checking:", url);


        const response = await fetch(
            url,
            {
                cache: "no-store",
                credentials: "same-origin"
            }
        );


        if (handleUnauthorized(response)) {
            return;
        }


        const data = await response.json();


        console.log(
            "Health response:",
            url,
            data
        );


        const connected =
            data.connected === true ||
            String(
                data.status || ""
            ).toLowerCase() === "connected";


        setStatus(
            elementId,
            connected
                ? "Connected"
                : "Disconnected",
            connected
                ? "connected"
                : "disconnected"
        );


    } catch (error) {

        console.error(
            "Health check failed:",
            url,
            error
        );


        setStatus(
            elementId,
            "Disconnected",
            "disconnected"
        );
    }
}


async function loadHealth() {

    console.log("loadHealth started");


    await Promise.all([
        checkService(
            "/api/kubernetes/status",
            "kubernetesStatus"
        ),

        checkService(
            "/api/prometheus/status",
            "prometheusStatus"
        ),

        checkService(
            "/api/grafana/status",
            "grafanaStatus"
        )
    ]);


    console.log("loadHealth finished");
}


// ============================================================
// NAMESPACES
// ============================================================

async function loadNamespaces() {

    try {

        const response = await fetch(
            "/api/namespaces",
            {
                cache: "no-store",
                credentials: "same-origin"
            }
        );


        if (handleUnauthorized(response)) {
            return;
        }


        if (!response.ok) {
            throw new Error(
                `Namespaces HTTP ${response.status}`
            );
        }


        const data = await response.json();

        const namespaces =
            data.namespaces || [];


        const investigationSelect =
            el("namespace");

        const metricsSelect =
            el("metricsNamespace");


        populateSelect(
            investigationSelect,
            namespaces
        );


        populateSelect(
            metricsSelect,
            namespaces
        );


        if (
            investigationSelect &&
            namespaces.includes("ai-sre")
        ) {
            investigationSelect.value =
                "ai-sre";
        }


        if (
            metricsSelect &&
            namespaces.includes("ai-sre")
        ) {
            metricsSelect.value =
                "ai-sre";
        }


        if (investigationSelect) {

            await loadDeployments(
                investigationSelect.value
            );
        }


    } catch (error) {

        console.error(
            "Namespace loading failed:",
            error
        );
    }
}


function populateSelect(select, values) {

    if (!select) {
        return;
    }


    select.innerHTML = "";


    values.forEach(value => {

        const option =
            document.createElement("option");

        option.value = value;
        option.textContent = value;

        select.appendChild(option);
    });
}


// ============================================================
// DEPLOYMENTS
// ============================================================

async function loadDeployments(namespace) {

    const select =
        el("deployment");


    if (!select) {
        return;
    }


    select.innerHTML =
        `<option value="">Loading...</option>`;


    try {

        const response = await fetch(
            `/api/deployments/${encodeURIComponent(namespace)}`,
            {
                cache: "no-store",
                credentials: "same-origin"
            }
        );


        if (handleUnauthorized(response)) {
            return;
        }


        if (!response.ok) {
            throw new Error(
                `Deployments HTTP ${response.status}`
            );
        }


        const data =
            await response.json();


        select.innerHTML =
            `<option value="">All deployments</option>`;


        (
            data.deployments || []
        ).forEach(name => {

            const option =
                document.createElement("option");

            option.value = name;
            option.textContent = name;

            select.appendChild(option);
        });


        if (
            (
                data.deployments || []
            ).includes("payment-api")
        ) {
            select.value =
                "payment-api";
        }


    } catch (error) {

        console.error(
            "Deployment loading failed:",
            error
        );


        select.innerHTML =
            `<option value="">All deployments</option>`;
    }
}


// ============================================================
// METRICS
// ============================================================

async function loadMetrics() {

    const namespace =
        el("metricsNamespace")?.value ||
        "ai-sre";


    try {

        const response = await fetch(
            `/api/metrics?namespace=${encodeURIComponent(namespace)}`,
            {
                cache: "no-store",
                credentials: "same-origin"
            }
        );


        if (handleUnauthorized(response)) {
            return;
        }


        if (!response.ok) {
            throw new Error(
                `Metrics HTTP ${response.status}`
            );
        }


        const data =
            await response.json();


        console.log(
            "Metrics:",
            data
        );


        setText(
            "runningPods",
            data.running_pods ?? "--"
        );

        setText(
            "failedPods",
            data.failed_pods ?? "--"
        );

        setText(
            "notReadyPods",
            data.not_ready_pods ?? "--"
        );

        setText(
            "containerRestarts",
            data.container_restarts ?? "--"
        );

        setText(
            "cpuUsage",
            data.cpu_usage ?? "--"
        );

        setText(
            "memoryUsage",
            data.memory_usage ?? "--"
        );


    } catch (error) {

        console.error(
            "Metrics failed:",
            error
        );
    }
}


// ============================================================
// INVESTIGATION
// ============================================================

async function investigate() {

    const question =
        el("question")?.value.trim();

    const namespace =
        el("namespace")?.value;

    const deployment =
        el("deployment")?.value || "";

    const button =
        el("investigateButton");

    const resultContainer =
        el("investigationResult");


    if (!question) {

        alert(
            "Please enter an investigation question."
        );

        return;
    }


    if (!namespace) {

        alert(
            "Please select a namespace."
        );

        return;
    }


    if (button) {

        button.disabled = true;

        button.textContent =
            "⏳ Investigating...";
    }


    showSection("results");


    if (resultContainer) {

        resultContainer.innerHTML = `

            <div class="loading-box">

                <div class="spinner"></div>

                <div>

                    <strong>
                        AI SRE Agent is investigating...
                    </strong>

                    <p>
                        Collecting Kubernetes evidence
                        and analyzing workload health.
                    </p>

                </div>

            </div>
        `;
    }


    try {

        const response = await fetch(
            "/api/investigate",
            {
                method: "POST",

                credentials: "same-origin",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    question,
                    namespace,
                    deployment:
                        deployment || null
                })
            }
        );


        if (handleUnauthorized(response)) {
            return;
        }


        const data =
            await response.json();


        console.log(
            "Investigation result:",
            data
        );


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "Investigation failed"
            );
        }


        renderInvestigationResult(
            data.result
        );


    } catch (error) {

        console.error(
            "Investigation error:",
            error
        );


        if (resultContainer) {

            resultContainer.innerHTML = `

                <div class="heal-failed">

                    ❌ Investigation failed

                    <br><br>

                    ${escapeHtml(error.message)}

                </div>
            `;
        }


    } finally {

        if (button) {

            button.disabled = false;

            button.textContent =
                "🔍 Investigate with AI";
        }
    }
}


// ============================================================
// REMEDIATION UI
// ============================================================

function buildRemediationHtml(result) {

    const remediation =
        result.remediation;


    if (!remediation) {
        return "";
    }


    const canHeal =
        remediation.auto_heal_eligible === true &&
        remediation.action === "rollout_restart" &&
        result.deployment &&
        result.deployment !== "All deployments";


    return `

        <div class="result-block remediation-block">

            <div class="remediation-header">

                <div>

                    <h3>
                        🤖 Automation Assessment
                    </h3>

                    <p>
                        AI SRE remediation policy decision
                    </p>

                </div>


                <span
                    class="risk-badge risk-${escapeHtml(
                        remediation.risk || "none"
                    )}"
                >

                    ${escapeHtml(
                        String(
                            remediation.risk || "none"
                        ).toUpperCase()
                    )} RISK

                </span>

            </div>


            <div class="remediation-grid">


                <div class="remediation-item">

                    <span>
                        PROPOSED ACTION
                    </span>

                    <strong>
                        ${escapeHtml(
                            remediation.action_label
                            || remediation.action
                        )}
                    </strong>

                </div>


                <div class="remediation-item">

                    <span>
                        CONFIDENCE
                    </span>

                    <strong>
                        ${remediation.confidence || 0}%
                    </strong>

                </div>


                <div class="remediation-item">

                    <span>
                        AUTO-HEAL ELIGIBLE
                    </span>

                    <strong
                        class="${
                            canHeal
                                ? "eligible-yes"
                                : "eligible-no"
                        }"
                    >
                        ${
                            canHeal
                                ? "YES"
                                : "NO"
                        }
                    </strong>

                </div>

            </div>


            <div class="remediation-reason">

                <span>
                    DECISION REASON
                </span>

                <p>
                    ${escapeHtml(
                        remediation.reason || "-"
                    )}
                </p>

            </div>


            ${
                canHeal
                ? `

                    <button
                        id="autoHealButton"
                        type="button"
                        class="autoheal-btn"
                    >
                        ⚡ Execute Auto-Heal
                    </button>


                    <div
                        id="autoHealStatus"
                        class="autoheal-status"
                    ></div>

                `
                : `

                    <div class="autoheal-blocked">

                        🔒 Automatic remediation blocked
                        by AI SRE policy.

                    </div>

                `
            }

        </div>
    `;
}


// ============================================================
// RESULT RENDERING
// ============================================================

function renderInvestigationResult(
    result
) {

    const container =
        el("investigationResult");


    if (!container) {
        return;
    }


    const severity =
        result.severity ||
        "Unknown";


    const severityClass =
        severity.toLowerCase();


    let podsHtml =
        `<div class="empty-evidence">
            No pod evidence found.
         </div>`;


    if (
        Array.isArray(result.pods) &&
        result.pods.length
    ) {

        podsHtml = `

            <div class="table-scroll">

                <table class="evidence-table">

                    <thead>

                        <tr>
                            <th>Pod</th>
                            <th>Ready</th>
                            <th>Status</th>
                            <th>Restarts</th>
                        </tr>

                    </thead>

                    <tbody>

                    ${
                        result.pods.map(
                            pod => `

                            <tr>

                                <td>
                                    <code>
                                        ${escapeHtml(pod.name)}
                                    </code>
                                </td>

                                <td>
                                    ${escapeHtml(pod.ready)}
                                </td>

                                <td>
                                    ${escapeHtml(pod.status)}
                                </td>

                                <td>
                                    ${pod.restarts ?? 0}
                                </td>

                            </tr>
                            `
                        ).join("")
                    }

                    </tbody>

                </table>

            </div>
        `;
    }


    let eventsHtml =
        `<div class="empty-evidence">
            No relevant events found.
         </div>`;


    if (
        Array.isArray(result.events) &&
        result.events.length
    ) {

        eventsHtml = `

            <div class="table-scroll">

                <table class="evidence-table">

                    <thead>

                        <tr>
                            <th>Type</th>
                            <th>Reason</th>
                            <th>Object</th>
                            <th>Message</th>
                        </tr>

                    </thead>

                    <tbody>

                    ${
                        result.events.map(
                            event => `

                            <tr>

                                <td>
                                    ${escapeHtml(event.type)}
                                </td>

                                <td>
                                    ${escapeHtml(event.reason)}
                                </td>

                                <td>
                                    ${escapeHtml(event.object)}
                                </td>

                                <td>
                                    ${escapeHtml(event.message)}
                                </td>

                            </tr>
                            `
                        ).join("")
                    }

                    </tbody>

                </table>

            </div>
        `;
    }


    const recommendations =
        Array.isArray(
            result.recommendations
        )
            ? result.recommendations
            : [];


    const remediationHtml =
        buildRemediationHtml(result);


    container.innerHTML = `

        <div class="result-summary">

            <div>

                <div class="eyebrow">
                    INVESTIGATION SUMMARY
                </div>

                <h2>
                    ${escapeHtml(
                        result.summary ||
                        "Investigation completed"
                    )}
                </h2>

            </div>


            <span
                class="severity severity-${severityClass}"
            >
                ${escapeHtml(severity)}
            </span>

        </div>


        <div class="context-grid">

            <div class="context-card">

                <span>
                    QUESTION
                </span>

                <strong>
                    ${escapeHtml(result.question)}
                </strong>

            </div>


            <div class="context-card">

                <span>
                    NAMESPACE
                </span>

                <strong>
                    ${escapeHtml(result.namespace)}
                </strong>

            </div>


            <div class="context-card">

                <span>
                    DEPLOYMENT
                </span>

                <strong>
                    ${escapeHtml(result.deployment)}
                </strong>

            </div>

        </div>


        <div class="result-block">

            <h3>
                🧠 Analysis
            </h3>

            <p>
                ${escapeHtml(result.analysis)}
            </p>

        </div>


        <div class="result-block root-cause">

            <h3>
                🎯 Root Cause Assessment
            </h3>

            <p>
                ${escapeHtml(result.root_cause)}
            </p>

        </div>


        <div class="result-block">

            <h3>
                ☸️ Kubernetes Pod Evidence
            </h3>

            ${podsHtml}

        </div>


        <div class="result-block">

            <h3>
                📋 Recent Cluster Events
            </h3>

            ${eventsHtml}

        </div>


        <div class="result-block">

            <h3>
                🛠 Recommended Remediation
            </h3>

            <ol class="recommendation-list">

                ${
                    recommendations.map(
                        recommendation => `

                        <li>
                            ${escapeHtml(recommendation)}
                        </li>

                        `
                    ).join("")
                }

            </ol>

        </div>


        ${remediationHtml}
    `;


    const autoHealButton =
        el("autoHealButton");


    if (
        autoHealButton &&
        result.remediation
    ) {

        autoHealButton.addEventListener(
            "click",
            () => {

                executeAutoHeal(
                    result.namespace,
                    result.deployment,
                    result.remediation.action
                );

            }
        );
    }
}


// ============================================================
// AUTO HEAL
// ============================================================

async function executeAutoHeal(
    namespace,
    deployment,
    action
) {

    const button =
        el("autoHealButton");

    const status =
        el("autoHealStatus");


    const confirmed =
        window.confirm(
            `Execute ${action} on\n\n` +
            `${namespace}/${deployment}?\n\n` +
            `This will restart the deployment.`
        );


    if (!confirmed) {
        return;
    }


    try {

        if (button) {

            button.disabled = true;

            button.textContent =
                "⏳ Healing...";
        }


        if (status) {

            status.innerHTML = `

                <div class="healing-progress">

                    ⏳ Executing remediation...

                </div>
            `;
        }


        const response = await fetch(
            "/api/remediate",
            {
                method: "POST",

                credentials: "same-origin",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    namespace,
                    deployment,
                    action
                })
            }
        );


        if (handleUnauthorized(response)) {
            return;
        }


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "Auto-Heal failed"
            );
        }


        if (status) {

            status.innerHTML = `

                <div class="heal-success">

                    ✅ ${escapeHtml(data.message)}

                    <br><br>

                    🔍 Monitoring recovery...

                </div>
            `;
        }


        setTimeout(
            async () => {

                await loadHealth();
                await loadMetrics();


                if (status) {

                    status.innerHTML += `

                        <div class="verification-message">

                            ✅ Monitoring refreshed.

                        </div>
                    `;
                }

            },
            8000
        );


    } catch (error) {

        console.error(
            "Auto-Heal error:",
            error
        );


        if (status) {

            status.innerHTML = `

                <div class="heal-failed">

                    ❌ ${escapeHtml(error.message)}

                </div>
            `;
        }


    } finally {

        if (button) {

            button.disabled = false;

            button.textContent =
                "⚡ Execute Auto-Heal";
        }
    }
}


// ============================================================
// GRAFANA
// ============================================================

async function openGrafana() {

    try {

        const response =
            await fetch(
                "/api/grafana/url",
                {
                    credentials: "same-origin"
                }
            );


        if (handleUnauthorized(response)) {
            return;
        }


        const data =
            await response.json();


        if (data.url) {

            window.open(
                data.url,
                "_blank",
                "noopener,noreferrer"
            );
        }


    } catch (error) {

        console.error(
            "Grafana open failed:",
            error
        );
    }
}


// ============================================================
// LOGOUT
// ============================================================

async function logout() {

    try {

        const response =
            await fetch(
                "/auth/logout",
                {
                    method: "POST",
                    credentials: "same-origin"
                }
            );


        if (!response.ok) {

            throw new Error(
                "Logout failed"
            );
        }


        window.location.href =
            "/login";


    } catch (error) {

        console.error(
            "Logout failed:",
            error
        );
    }
}


// ============================================================
// EVENTS
// ============================================================

function setupEvents() {

    document
        .querySelectorAll(".nav-item")
        .forEach(button => {

            button.addEventListener(
                "click",
                () => {

                    showSection(
                        button.dataset.section
                    );
                }
            );
        });


    document
        .querySelectorAll("[data-go-section]")
        .forEach(button => {

            button.addEventListener(
                "click",
                () => {

                    showSection(
                        button.dataset.goSection
                    );
                }
            );
        });


    el("refreshAllButton")
        ?.addEventListener(
            "click",
            async () => {

                await Promise.all([
                    loadHealth(),
                    loadMetrics()
                ]);
            }
        );


    el("healthRefreshButton")
        ?.addEventListener(
            "click",
            loadHealth
        );


    el("metricsRefreshButton")
        ?.addEventListener(
            "click",
            loadMetrics
        );


    el("metricsNamespace")
        ?.addEventListener(
            "change",
            loadMetrics
        );


    el("namespace")
        ?.addEventListener(
            "change",
            event => {

                loadDeployments(
                    event.target.value
                );
            }
        );


    el("investigateButton")
        ?.addEventListener(
            "click",
            investigate
        );


    el("startInvestigationButton")
        ?.addEventListener(
            "click",
            () => {
                showSection(
                    "investigate"
                );
            }
        );


    el("openGrafanaButton")
        ?.addEventListener(
            "click",
            openGrafana
        );


    el("logoutButton")
        ?.addEventListener(
            "click",
            logout
        );


    document
        .querySelectorAll(
            ".quick-question"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                () => {

                    const question =
                        el("question");


                    if (question) {

                        question.value =
                            button.dataset.question;
                    }
                }
            );
        });
}


// ============================================================
// INITIALIZATION
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    async () => {

        console.log(
            "AI SRE DOM ready"
        );


        try {

            setupEvents();


            await loadNamespaces();


            await Promise.all([
                loadHealth(),
                loadMetrics()
            ]);


            console.log(
                "AI SRE initialization complete"
            );


        } catch (error) {

            console.error(
                "AI SRE initialization failed:",
                error
            );
        }
    }
);


// Expose for debugging
window.loadHealth = loadHealth;
window.loadMetrics = loadMetrics;
window.investigate = investigate;
window.executeAutoHeal = executeAutoHeal;
