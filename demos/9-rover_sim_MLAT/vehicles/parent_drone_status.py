from enum import Enum

class ParentDroneStatus(Enum):
    IDLE = "idle"
    COLLECTING_MEASUREMENTS = "collecting_measurements"
    CALCULATING_POSITION = "calculating_position"
    REPOSITIONING_DRONES = "repositioning_drones"
    SENDING_POSITION = "sending_position"
    ERROR = "error"