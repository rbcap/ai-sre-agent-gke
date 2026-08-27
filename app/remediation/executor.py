from datetime import datetime, timezone

from kubernetes import client


def rollout_restart(
    namespace: str,
    deployment: str
):

    apps_v1 = client.AppsV1Api()

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()


    patch = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "ai-sre/restartedAt":
                            timestamp
                    }
                }
            }
        }
    }


    apps_v1.patch_namespaced_deployment(
        name=deployment,
        namespace=namespace,
        body=patch
    )


    return {
        "success": True,
        "action": "rollout_restart",
        "deployment": deployment,
        "namespace": namespace
    }
