from enum import Enum


class UserRole(str, Enum):
    user = "user"
    admin = "admin"

class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"

class EmailStatus(str, Enum):
    UNREAD = "UNREAD"
    TO_CLASSIFY = "TO_CLASSIFY"
    TO_RESPOND = "TO_RESPOND"
    DRAFT = "DRAFT"
    ESCALATED = "ESCALATED"
    SENT = "SENT"
    IGNORED = "IGNORED"
    FAILED = "FAILED"