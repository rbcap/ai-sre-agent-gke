import time

from kubernetes import client


def verify_deployment(
    namespace: str,
    deployment: str,
    timeout: int = 120
):

    apps_v1 = client.AppsV1Api()

    start = time.time()


    while time.time() - start < timeout:

        obj = apps_v1.read_namespaced_deployment_status(
            name=deployment,
            namespace=namespace
        )


        desired = obj.spec.replicas or 0

        available = (
            obj.status.available_replicas
            or 0
        )


        if available >= desired:

            return {
                "healthy": True,
                "desired": desired,
                "available": available
            }


        time.sleep(5)


    return {
        "healthy": False,
        "reason": "Verification timeout"
    }
