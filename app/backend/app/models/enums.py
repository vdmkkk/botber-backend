import enum

class InstanceStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    not_enough_balance = "not_enough_balance"
