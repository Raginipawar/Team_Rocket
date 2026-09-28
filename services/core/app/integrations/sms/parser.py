"""A's file (work-distribution.md §2.2). SMS inbound parsing order
(technical.md §12.1):
1. `GH <id> <CMD>` -> paramedic fallback command.
2. `YES` -> prank verification.
3. An open emergency with a pending follow-up question, from this phone -> answer.
4. Otherwise -> new emergency.

Real gateway account (textbee/httpSMS) + phone hardware deferred by the user
to a later session -- this module is the actual routing logic, testable
independently of which gateway eventually calls the webhook."""

import re
from dataclasses import dataclass
from typing import Literal

GH_COMMAND_RE = re.compile(r"^\s*GH\s+(\S+)\s+(\w+)", re.IGNORECASE)
FOLLOWUP_ANSWER_WINDOW_MIN = 60


@dataclass
class ParamedicCommand:
    kind: Literal["paramedic_command"] = "paramedic_command"
    emergency_short_id: str = ""
    command: str = ""


@dataclass
class PrankVerification:
    kind: Literal["prank_verification"] = "prank_verification"


@dataclass
class FollowupAnswer:
    kind: Literal["followup_answer"] = "followup_answer"
    emergency_id: str = ""
    question_id: str = ""


@dataclass
class NewEmergency:
    kind: Literal["new_emergency"] = "new_emergency"


ParsedInbound = ParamedicCommand | PrankVerification | FollowupAnswer | NewEmergency


def parse_inbound(body: str, open_followup: dict | None) -> ParsedInbound:
    """`open_followup`, if given, is {"emergency_id": ..., "question_id": ...}
    for the caller's most recent open emergency with a pending question,
    already filtered by the caller (§12.1: 'replies... matched to the open
    emergency for that phone, latest, < 60 min') -- that lookup is a DB query
    the caller (webhooks_sms.py) does, this function is pure."""
    stripped = body.strip()

    match = GH_COMMAND_RE.match(stripped)
    if match:
        return ParamedicCommand(emergency_short_id=match.group(1), command=match.group(2).upper())

    if stripped.strip().upper() == "YES":
        return PrankVerification()

    if open_followup is not None:
        return FollowupAnswer(emergency_id=open_followup["emergency_id"], question_id=open_followup["question_id"])

    return NewEmergency()
