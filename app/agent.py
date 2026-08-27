import json
import os

from google import genai
from google.genai.types import HttpOptions

from app.tools.kubernetes_tools import (
    get_deployment_spec,
    get_deployments,
    get_pod_logs,
    get_pods,
    get_recent_events,
)


PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-east1")

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
    http_options=HttpOptions(api_version="v1"),
)


def collect_incident_evidence(
    namespace: str,
    deployment_name: str | None = None,
) -> dict:
    """
    Collect real Kubernetes evidence for an SRE investigation.

    The function gathers:
    - Pod health and container status
    - Deployment health
    - Recent Kubernetes events
    - Relevant deployment configuration
    - Current and previous container logs
    """

    # Collect general namespace evidence
    pods = get_pods(namespace)
    deployments = get_deployments(namespace)
    events = get_recent_events(namespace)

    # Default deployment configuration
    deployment_spec = None

    # If a specific deployment is being investigated,
    # collect and filter evidence for that deployment.
    if deployment_name:
        deployment_spec = get_deployment_spec(
            namespace=namespace,
            deployment_name=deployment_name,
        )

        deployments = [
            deployment
            for deployment in deployments
            if deployment["name"] == deployment_name
        ]

        pods = [
            pod
            for pod in pods
            if pod["name"].startswith(f"{deployment_name}-")
        ]

    # Collect logs for every relevant pod
    logs = {}

    for pod in pods:
        pod_name = pod["name"]

        logs[pod_name] = get_pod_logs(
            namespace=namespace,
            pod_name=pod_name,
        )

    # Return one structured evidence bundle for the AI agent
    return {
        "namespace": namespace,
        "deployment": deployment_name,
        "deployment_spec": deployment_spec,
        "pods": pods,
        "deployments": deployments,
        "events": events,
        "logs": logs,
    }

def investigate_incident(
    question: str,
    namespace: str = "ai-sre",
    deployment_name: str | None = None,
) -> str:
    """Collect real Kubernetes evidence and ask Gemini for RCA."""

    evidence = collect_incident_evidence(
        namespace=namespace,
        deployment_name=deployment_name,
    )

    evidence_json = json.dumps(
        evidence,
        indent=2,
        default=str,
    )

    prompt = f"""
You are a senior Site Reliability Engineer performing an evidence-based
Kubernetes incident investigation.

User question:
{question}

REAL EVIDENCE COLLECTED FROM THE GKE CLUSTER:

{evidence_json}

Analyze the incident using the following strict rules:

1. Treat the evidence above as the source of truth.
2. Clearly distinguish FACTS from HYPOTHESES.
3. Do not invent logs, metrics, events, or Kubernetes states.
4. Do not claim a root cause with certainty unless directly supported.
5. If evidence is insufficient, specify exactly what additional evidence
   should be collected.
6. Do not recommend destructive actions.
7. Prioritize the safest remediation.

Return the response in this exact structure:

## INCIDENT SUMMARY

## IMPACT ASSESSMENT

## OBSERVED EVIDENCE

## MOST LIKELY ROOT CAUSE

## ALTERNATIVE HYPOTHESES

## RECOMMENDED INVESTIGATION

## RECOMMENDED REMEDIATION

## RISK LEVEL

## CONFIDENCE

## EVIDENCE GAPS
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text
