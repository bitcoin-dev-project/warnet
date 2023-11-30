from enum import Enum


class Status(Enum):
    PENDING = 1
    RUNNING = 2
    STOPPED = 3
    FAILED = 4
    UNKNOWN = 5