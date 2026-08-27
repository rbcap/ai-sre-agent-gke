from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
from kubernetes.client.rest import ApiException


def load_kubernetes_client():
    """
    Configure the Kubernetes client.

    Priority:
    1. In-cluster configuration when running inside Kubernetes.
    2. Local kubeconfig when running locally.
    """

    try:
        config.load_incluster_config()
        print("Using in-cluster Kubernetes configuration")
    except ConfigException:
        try:
            config.load_kube_config()
            print("Using local kubeconfig")
        except ConfigException as error:
            raise RuntimeError(
                "Unable to load Kubernetes configuration. "
                "Run inside a Kubernetes cluster or provide a valid kubeconfig."
            ) from error

load_kubernetes_client()

core_v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()


def get_pods(namespace: str) -> list:
    """Get pod status and container health information."""

    pods = core_v1.list_namespaced_pod(namespace=namespace)
    results = []

    for pod in pods.items:
        containers = []

        for container_status in pod.status.container_statuses or []:
            state = "Unknown"

            if container_status.state.waiting:
                state = container_status.state.waiting.reason or "Waiting"
            elif container_status.state.terminated:
                state = container_status.state.terminated.reason or "Terminated"
            elif container_status.state.running:
                state = "Running"

            last_reason = None
            exit_code = None

            if (
                container_status.last_state
                and container_status.last_state.terminated
            ):
                last_reason = container_status.last_state.terminated.reason
                exit_code = container_status.last_state.terminated.exit_code

            containers.append(
                {
                    "name": container_status.name,
                    "ready": container_status.ready,
                    "restart_count": container_status.restart_count,
                    "state": state,
                    "last_termination_reason": last_reason,
                    "exit_code": exit_code,
                }
            )

        results.append(
            {
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "pod_ip": pod.status.pod_ip,
                "containers": containers,
            }
        )

    return results


def get_recent_events(namespace: str, limit: int = 20) -> list:
    """Get recent Kubernetes events."""

    events = core_v1.list_namespaced_event(namespace=namespace)

    sorted_events = sorted(
        events.items,
        key=lambda event: (
            event.last_timestamp
            or event.event_time
            or event.metadata.creation_timestamp
        ),
        reverse=True,
    )

    results = []

    for event in sorted_events[:limit]:
        results.append(
            {
                "type": event.type,
                "reason": event.reason,
                "message": event.message,
                "object": (
                    f"{event.involved_object.kind}/"
                    f"{event.involved_object.name}"
                ),
            }
        )

    return results


def get_deployments(namespace: str) -> list:
    """Get deployment health information."""

    deployments = apps_v1.list_namespaced_deployment(
        namespace=namespace
    )

    results = []

    for deployment in deployments.items:
        desired = deployment.spec.replicas or 0
        ready = deployment.status.ready_replicas or 0
        available = deployment.status.available_replicas or 0

        results.append(
            {
                "name": deployment.metadata.name,
                "desired_replicas": desired,
                "ready_replicas": ready,
                "available_replicas": available,
                "unavailable_replicas": desired - available,
            }
        )

    return results


def get_pod_logs(
    namespace: str,
    pod_name: str,
    tail_lines: int = 100,
) -> dict:
    """
    Collect both current and previous container logs.

    Previous logs are useful for CrashLoopBackOff.
    Current logs may still contain useful evidence when previous logs
    are unavailable.
    """

    result = {
        "current": None,
        "previous": None,
        "errors": {},
    }

    try:
        result["current"] = core_v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=tail_lines,
            previous=False,
        )
    except ApiException as error:
        result["errors"]["current"] = str(error)

    try:
        result["previous"] = core_v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=tail_lines,
            previous=True,
        )
    except ApiException as error:
        result["errors"]["previous"] = str(error)

    return result
def get_deployment_spec(namespace: str, deployment_name: str) -> dict:
    """Get relevant deployment configuration for investigation."""

    try:
        deployment = apps_v1.read_namespaced_deployment(
            name=deployment_name,
            namespace=namespace,
        )

        containers = []

        for container in deployment.spec.template.spec.containers:
            containers.append(
                {
                    "name": container.name,
                    "image": container.image,
                    "command": container.command,
                    "args": container.args,
                    "env": [
                        {
                            "name": env.name,
                            "value": env.value,
                            "value_from": (
                                str(env.value_from)
                                if env.value_from
                                else None
                            ),
                        }
                        for env in (container.env or [])
                    ],
                }
            )

        return {
            "name": deployment.metadata.name,
            "replicas": deployment.spec.replicas,
            "containers": containers,
        }

    except ApiException as error:
        return {
            "error": error.reason,
        }
