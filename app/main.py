import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from fastapi import (
    FastAPI,
    Request,
    Depends,
    HTTPException,
)

from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel

from kubernetes import client, config

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from starlette.middleware.sessions import SessionMiddleware


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-sre")


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="AI SRE Agent",
    description="AI-powered Kubernetes Incident Investigation Platform",
    version="1.0.0",
)

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR)
)


# ============================================================
# CONFIGURATION
# ============================================================

PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://127.0.0.1:9090",
)

GRAFANA_URL = os.getenv(
    "GRAFANA_URL",
    "http://34.24.35.118",
)

GOOGLE_CLIENT_ID = os.getenv(
    "GOOGLE_CLIENT_ID",
    "",
)

SESSION_SECRET = os.getenv(
    "SESSION_SECRET",
    "change-this-secret-before-production",
)

COOKIE_SECURE = (
    os.getenv("COOKIE_SECURE", "false").lower()
    == "true"
)

ALLOWED_EMAIL = os.getenv(
    "AI_SRE_ALLOWED_EMAIL",
    "",
).strip().lower()


# ============================================================
# SESSION
# ============================================================

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="ai_sre_session",
    max_age=3600,
    same_site="lax",
    https_only=COOKIE_SECURE,
)


# ============================================================
# MODELS
# ============================================================

class GoogleLoginRequest(BaseModel):
    credential: str


class InvestigationRequest(BaseModel):
    question: str
    namespace: str = "ai-sre"
    deployment: Optional[str] = None


class RemediationRequest(BaseModel):
    namespace: str
    deployment: str
    action: str


# ============================================================
# KUBERNETES AUTH
# ============================================================

def load_kubernetes_config():

    try:
        config.load_incluster_config()

        logger.info(
            "Kubernetes authentication: in-cluster"
        )

        return

    except Exception:
        logger.info(
            "In-cluster authentication unavailable; "
            "trying local kubeconfig"
        )

    config.load_kube_config()

    logger.info(
        "Kubernetes authentication: local kubeconfig"
    )


# ============================================================
# AUTH DEPENDENCY
# ============================================================

def require_auth(request: Request):

    user = request.session.get("user")

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    return user


# ============================================================
# LOGIN PAGE
# ============================================================

@app.get("/login")
async def login_page(request: Request):

    if request.session.get("user"):
        return RedirectResponse(
            url="/",
            status_code=302,
        )

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "google_client_id": GOOGLE_CLIENT_ID,
        },
    )


# ============================================================
# GOOGLE LOGIN
# ============================================================

@app.post("/auth/google")
async def google_login(
    payload: GoogleLoginRequest,
    request: Request,
):

    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLIENT_ID is not configured",
        )

    try:
        token_data = id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )

        email = (
            token_data.get("email", "")
            .strip()
            .lower()
        )

        if not email:
            raise HTTPException(
                status_code=401,
                detail="Google account email unavailable",
            )

        if not token_data.get(
            "email_verified",
            False,
        ):
            raise HTTPException(
                status_code=403,
                detail="Google email is not verified",
            )

        if (
            ALLOWED_EMAIL
            and email != ALLOWED_EMAIL
        ):
            raise HTTPException(
                status_code=403,
                detail="Google account not authorized",
            )

        user = {
            "sub": token_data.get("sub"),
            "email": email,
            "name": token_data.get(
                "name",
                email,
            ),
            "picture": token_data.get(
                "picture",
                "",
            ),
        }

        request.session["user"] = user

        logger.info(
            "Google login successful: %s",
            email,
        )

        return {
            "success": True,
            "user": user,
        }

    except HTTPException:
        raise

    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid Google ID token",
        )

    except Exception as error:
        logger.exception(
            "Google authentication failed"
        )

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# LOGOUT
# ============================================================

@app.post("/auth/logout")
async def logout(request: Request):

    request.session.clear()

    return {
        "success": True,
    }


# ============================================================
# CURRENT USER
# ============================================================

@app.get("/api/me")
async def current_user(
    user=Depends(require_auth),
):

    return {
        "authenticated": True,
        "user": user,
    }


# ============================================================
# HOME
# ============================================================

@app.get("/")
async def home(request: Request):

    user = request.session.get("user")

    if not user:
        return RedirectResponse(
            url="/login",
            status_code=302,
        )

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "grafana_url": GRAFANA_URL,
            "user": user,
        },
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():

    return {
        "status": "healthy",
        "service": "AI SRE Agent",
    }


# ============================================================
# NAMESPACES
# ============================================================

@app.get("/api/namespaces")
async def get_namespaces(
    user=Depends(require_auth),
):

    load_kubernetes_config()

    v1 = client.CoreV1Api()

    response = v1.list_namespace()

    namespaces = sorted(
        item.metadata.name
        for item in response.items
    )

    return {
        "success": True,
        "namespaces": namespaces,
    }


# ============================================================
# DEPLOYMENTS
# ============================================================

@app.get("/api/deployments/{namespace}")
async def get_deployments(
    namespace: str,
    user=Depends(require_auth),
):

    load_kubernetes_config()

    apps_v1 = client.AppsV1Api()

    response = (
        apps_v1.list_namespaced_deployment(
            namespace=namespace
        )
    )

    deployments = sorted(
        item.metadata.name
        for item in response.items
    )

    return {
        "success": True,
        "namespace": namespace,
        "deployments": deployments,
    }


# ============================================================
# KUBERNETES STATUS
# ============================================================

@app.get("/api/kubernetes/status")
async def kubernetes_status(
    user=Depends(require_auth),
):

    try:
        load_kubernetes_config()

        v1 = client.CoreV1Api()

        v1.list_namespace(limit=1)

        return {
            "connected": True,
            "status": "Connected",
        }

    except Exception as error:
        return {
            "connected": False,
            "status": "Disconnected",
            "error": str(error),
        }


# ============================================================
# PROMETHEUS STATUS
# ============================================================

@app.get("/api/prometheus/status")
async def prometheus_status(
    user=Depends(require_auth),
):

    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/-/ready",
            timeout=5,
        )

        connected = (
            response.status_code == 200
        )

        return {
            "connected": connected,
            "status": (
                "Connected"
                if connected
                else "Disconnected"
            ),
        }

    except Exception as error:
        return {
            "connected": False,
            "status": "Disconnected",
            "error": str(error),
        }


# ============================================================
# GRAFANA STATUS
# ============================================================

@app.get("/api/grafana/status")
async def grafana_status(
    user=Depends(require_auth),
):

    try:
        response = requests.get(
            f"{GRAFANA_URL}/api/health",
            timeout=5,
        )

        connected = (
            response.status_code == 200
        )

        return {
            "connected": connected,
            "status": (
                "Connected"
                if connected
                else "Disconnected"
            ),
            "url": GRAFANA_URL,
        }

    except Exception as error:
        return {
            "connected": False,
            "status": "Disconnected",
            "url": GRAFANA_URL,
            "error": str(error),
        }


@app.get("/api/grafana/url")
async def grafana_url(
    user=Depends(require_auth),
):

    return {
        "url": GRAFANA_URL,
    }


# ============================================================
# METRICS
# ============================================================

@app.get("/api/metrics")
async def get_metrics(
    namespace: str = "ai-sre",
    user=Depends(require_auth),
):

    metrics = {
        "namespace": namespace,
        "running_pods": 0,
        "failed_pods": 0,
        "not_ready_pods": 0,
        "container_restarts": 0,
        "cpu_usage": "N/A",
        "memory_usage": "N/A",
    }

    try:
        load_kubernetes_config()

        v1 = client.CoreV1Api()

        pods = v1.list_namespaced_pod(
            namespace=namespace
        )

        for pod in pods.items:

            if pod.status.phase == "Running":
                metrics["running_pods"] += 1

            if pod.status.phase == "Failed":
                metrics["failed_pods"] += 1

            ready = False

            for condition in (
                pod.status.conditions or []
            ):
                if (
                    condition.type == "Ready"
                    and condition.status == "True"
                ):
                    ready = True
                    break

            if not ready:
                metrics["not_ready_pods"] += 1

            for container_status in (
                pod.status.container_statuses
                or []
            ):
                metrics["container_restarts"] += (
                    container_status.restart_count
                    or 0
                )

        return metrics

    except Exception as error:
        metrics["error"] = str(error)
        return metrics


# ============================================================
# INVESTIGATION
# ============================================================

@app.post("/api/investigate")
async def investigate(
    request: InvestigationRequest,
    user=Depends(require_auth),
):

    namespace = (
        request.namespace.strip()
        or "ai-sre"
    )

    deployment = (
        request.deployment.strip()
        if request.deployment
        else ""
    )

    question = (
        request.question.strip()
    )

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Investigation question is required",
        )

    try:
        load_kubernetes_config()

        v1 = client.CoreV1Api()

        # ----------------------------------------------------
        # PODS
        # ----------------------------------------------------

        pods_response = (
            v1.list_namespaced_pod(
                namespace=namespace
            )
        )

        pods = []

        for pod in pods_response.items:

            pod_name = pod.metadata.name

            if (
                deployment
                and deployment not in pod_name
            ):
                continue

            container_statuses = (
                pod.status.container_statuses
                or []
            )

            restart_count = 0
            ready_count = 0

            status_text = (
                pod.status.phase
                or "Unknown"
            )

            for container_status in (
                container_statuses
            ):

                restart_count += (
                    container_status.restart_count
                    or 0
                )

                if container_status.ready:
                    ready_count += 1

                state = (
                    container_status.state
                )

                if (
                    state
                    and state.waiting
                ):
                    status_text = (
                        state.waiting.reason
                        or status_text
                    )

                elif (
                    state
                    and state.terminated
                ):
                    status_text = (
                        state.terminated.reason
                        or status_text
                    )

            pods.append(
                {
                    "name": pod_name,
                    "ready": (
                        f"{ready_count}/"
                        f"{len(container_statuses)}"
                    ),
                    "status": status_text,
                    "restarts": restart_count,
                }
            )

        # ----------------------------------------------------
        # EVENTS
        # ----------------------------------------------------

        events_response = (
            v1.list_namespaced_event(
                namespace=namespace
            )
        )

        events = []

        for event in (
            events_response.items[-20:]
        ):

            object_name = (
                event.involved_object.name
                if event.involved_object
                else ""
            )

            if (
                deployment
                and deployment not in object_name
            ):
                continue

            events.append(
                {
                    "type": (
                        event.type
                        or "Normal"
                    ),
                    "reason": (
                        event.reason
                        or "Unknown"
                    ),
                    "object": object_name,
                    "message": (
                        event.message
                        or ""
                    ),
                }
            )

        # ----------------------------------------------------
        # RCA
        # ----------------------------------------------------

        crashloop_pods = [
            pod
            for pod in pods
            if (
                "CrashLoopBackOff"
                in pod["status"]
            )
        ]

        unhealthy_pods = [
            pod
            for pod in pods
            if (
                pod["status"]
                not in [
                    "Running",
                    "Succeeded",
                ]
                or pod["restarts"] > 0
            )
        ]

        if crashloop_pods:

            severity = "Critical"

            root_cause = (
                f"{len(crashloop_pods)} pod(s) "
                "are in CrashLoopBackOff."
            )

            recommendations = [
                "Check previous container logs.",
                "Verify environment variables, Secrets and ConfigMaps.",
                "Review application startup configuration.",
                "Inspect Kubernetes BackOff events.",
            ]

        elif unhealthy_pods:

            severity = "Warning"

            root_cause = (
                f"{len(unhealthy_pods)} unhealthy pod(s) detected."
            )

            recommendations = [
                "Review pod readiness.",
                "Inspect Kubernetes events.",
                "Check application logs.",
            ]

        else:

            severity = "Healthy"

            root_cause = (
                "No critical pod failures detected."
            )

            recommendations = [
                "Continue monitoring the workload."
            ]

        # ----------------------------------------------------
        # REMEDIATION INTELLIGENCE
        # ----------------------------------------------------

        remediation = {
            "action": "none",
            "action_label": "No Automated Action",
            "risk": "none",
            "confidence": 0,
            "auto_heal_eligible": False,
            "requires_approval": False,
            "reason": (
                "No safe automated remediation identified."
            ),
        }

        root_cause_lower = (
            root_cause.lower()
        )

        configuration_problem = any(
            keyword in root_cause_lower
            for keyword in [
                "secret",
                "config",
                "configuration",
                "environment variable",
                "database_url",
                "missing variable",
            ]
        )

        if configuration_problem:

            remediation = {
                "action": "configuration_fix",
                "action_label": (
                    "Configuration Fix Required"
                ),
                "risk": "high",
                "confidence": 96,
                "auto_heal_eligible": False,
                "requires_approval": True,
                "reason": (
                    "The incident appears configuration-related. "
                    "Restarting the workload would not resolve "
                    "the underlying issue."
                ),
            }

        elif crashloop_pods:

            remediation = {
                "action": "rollout_restart",
                "action_label": "Rollout Restart",
                "risk": "low",
                "confidence": 90,
                "auto_heal_eligible": True,
                "requires_approval": True,
                "reason": (
                    f"{len(crashloop_pods)} pod(s) are repeatedly "
                    "entering CrashLoopBackOff. A controlled "
                    "rollout restart can be attempted."
                ),
            }

        elif unhealthy_pods:

            remediation = {
                "action": "none",
                "action_label": (
                    "Manual Investigation Required"
                ),
                "risk": "medium",
                "confidence": 75,
                "auto_heal_eligible": False,
                "requires_approval": True,
                "reason": (
                    "The evidence is not strong enough "
                    "for a safe automatic action."
                ),
            }

        return {
            "success": True,
            "result": {
                "summary": (
                    "AI SRE investigation "
                    "completed successfully."
                ),
                "question": question,
                "namespace": namespace,
                "deployment": (
                    deployment
                    or "All deployments"
                ),
                "severity": severity,
                "analysis": (
                    f"Investigation completed for "
                    f"namespace '{namespace}'. "
                    "Kubernetes pod health, restart "
                    "activity and cluster events "
                    "were analyzed."
                ),
                "root_cause": root_cause,
                "pods": pods,
                "events": events,
                "recommendations": recommendations,
                "remediation": remediation,
            },
        }

    except Exception as error:

        logger.exception(
            "Investigation failed"
        )

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# AUTO-HEAL
# ============================================================

@app.post("/api/remediate")
async def remediate(
    request: RemediationRequest,
    user=Depends(require_auth),
):

    allowed_actions = {
        "rollout_restart"
    }

    if (
        request.action
        not in allowed_actions
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "This remediation action is not "
                "allowed by policy."
            ),
        )

    if not request.namespace:
        raise HTTPException(
            status_code=400,
            detail="Namespace is required.",
        )

    if not request.deployment:
        raise HTTPException(
            status_code=400,
            detail="Deployment is required.",
        )

    try:
        load_kubernetes_config()

        apps_v1 = client.AppsV1Api()

        apps_v1.read_namespaced_deployment(
            name=request.deployment,
            namespace=request.namespace,
        )

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        patch = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "ai-sre/restartedAt":
                                timestamp,
                            "ai-sre/triggeredBy":
                                user.get(
                                    "email",
                                    "unknown",
                                ),
                        }
                    }
                }
            }
        }

        apps_v1.patch_namespaced_deployment(
            name=request.deployment,
            namespace=request.namespace,
            body=patch,
        )

        logger.info(
            "Auto-heal rollout restart: %s/%s user=%s",
            request.namespace,
            request.deployment,
            user.get("email"),
        )

        return {
            "success": True,
            "action": request.action,
            "namespace": request.namespace,
            "deployment": request.deployment,
            "message": (
                f"Rollout restart initiated for "
                f"{request.namespace}/"
                f"{request.deployment}."
            ),
        }

    except Exception as error:

        logger.exception(
            "Auto-heal failed"
        )

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )
