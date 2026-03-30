"""Project constants and enums."""

from __future__ import annotations
from enum import Enum


class Role(str, Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"


class SSSLevel(str, Enum):
    sss1 = "SSS1"
    sss2 = "SSS2"
    sss3 = "SSS3"


class Term(int, Enum):
    term1 = 1
    term2 = 2
    term3 = 3


class TutorMode(str, Enum):
    explain = "explain"
    practice = "practice"
    revise = "revise"
    exam_prep = "exam_prep"
