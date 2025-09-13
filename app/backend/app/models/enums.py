import enum

class InstanceStatus(str, enum.Enum):
    active = "active"
    paused = "paused" # legacy lmao
    not_enough_balance = "not_enough_balance"

    provisioning = "provisioning"
    inactive = "inactive"          # external “deactivate”
    updating = "updating"
    deleting = "deleting"
    error = "error"
    unknown = "unknown"