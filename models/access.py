from enum import Enum


class UserRole(str, Enum):
    CITIZEN = "citizen"
    GOVERNMENT_OFFICER = "government_officer"
    DEPARTMENT_MANAGER = "department_manager"
    ADMINISTRATOR = "administrator"


class DocumentClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"
