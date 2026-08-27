REMEDIATION_POLICIES = {

    "restart_pod": {
        "risk": "low",
        "auto_execute": True,
        "requires_approval": False
    },

    "rollout_restart": {
        "risk": "low",
        "auto_execute": True,
        "requires_approval": False
    },

    "scale_up": {
        "risk": "medium",
        "auto_execute": False,
        "requires_approval": True
    },

    "update_image": {
        "risk": "high",
        "auto_execute": False,
        "requires_approval": True
    },

    "modify_config": {
        "risk": "high",
        "auto_execute": False,
        "requires_approval": True
    },

    "modify_secret": {
        "risk": "critical",
        "auto_execute": False,
        "requires_approval": True
    }
}
