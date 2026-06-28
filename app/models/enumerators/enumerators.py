from enum import Enum


class UserRole(str, Enum):
    user = "user"
    admin = "admin"

class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"

class TemplateStatus(str, Enum):
    ACTIVE = "ACTIVE"                       # creato dall'umano o approvato
    PENDING_APPROVAL = "PENDING_APPROVAL"   # proposto dall'agente, in attesa
    REJECTED = "REJECTED"                   # rifiutato dall'operatore

class EmailStatus(str, Enum):
    UNREAD = "UNREAD"
    TO_CLASSIFY = "TO_CLASSIFY"
    TO_RESPOND = "TO_RESPOND"
    DRAFT = "DRAFT"
    ESCALATED = "ESCALATED"
    SENT = "SENT"
    IGNORED = "IGNORED"
    FAILED = "FAILED"