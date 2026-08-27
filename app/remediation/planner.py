from .policies import REMEDIATION_POLICIES


def build_remediation_plan(
    root_cause: str,
    pods: list,
    deployment: str
):

    root_cause_lower = root_cause.lower()


    # CrashLoop with high restarts
    if (
        "crashloopbackoff" in root_cause_lower
        or any(
            "CrashLoopBackOff" in pod.get("status", "")
            for pod in pods
        )
    ):

        action = "rollout_restart"

        policy = REMEDIATION_POLICIES[action]

        return {
            "action": action,
            "target": deployment,
            "risk": policy["risk"],
            "auto_execute": policy["auto_execute"],
            "requires_approval": policy["requires_approval"],
            "reason": (
                "Workload contains containers repeatedly "
                "entering CrashLoopBackOff."
            )
        }


    # Missing configuration
    if (
        "environment variable" in root_cause_lower
        or "config" in root_cause_lower
        or "secret" in root_cause_lower
    ):

        action = "modify_config"

        policy = REMEDIATION_POLICIES[action]

        return {
            "action": action,
            "target": deployment,
            "risk": policy["risk"],
            "auto_execute": False,
            "requires_approval": True,
            "reason": (
                "Application configuration change detected. "
                "Automatic modification is blocked."
            )
        }


    return {
        "action": "none",
        "risk": "none",
        "auto_execute": False,
        "requires_approval": False,
        "reason": "No safe automated remediation identified."
    }
