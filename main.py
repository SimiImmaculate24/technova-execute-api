# main.py
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import re
import json
from collections import OrderedDict

app = FastAPI(title="TechNova Assistant Function Router")

# Enable CORS for any origin (allow GET)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# --- Helper: build response ensuring argument order ---
def build_response(func_name: str, ordered_args: OrderedDict):
    """
    Return the required JSON structure:
    {
      "name": "function_name",
      "arguments": "{\"arg1\": value1, \"arg2\": value2}"
    }
    The arguments value is a JSON-encoded string (keys in insertion order).
    """
    # json.dumps will preserve insertion order for OrderedDict
    args_str = json.dumps(ordered_args, ensure_ascii=False)
    return {"name": func_name, "arguments": args_str}


# --- Regex patterns to extract parameters ---
# Patterns are intentionally strict for the templated example sentences.
PATTERNS = [
    # Ticket Status: "What is the status of ticket 83742?"
    {
        "name": "get_ticket_status",
        "pattern": re.compile(r"\bstatus of ticket\s+(\d+)\b", re.IGNORECASE),
        "arg_keys": ["ticket_id"],
        "arg_types": [int],
    },
    # Meeting Scheduling:
    # "Schedule a meeting on 2025-02-15 at 14:00 in Room A."
    {
        "name": "schedule_meeting",
        "pattern": re.compile(
            r"\bschedule a meeting on\s+([0-9]{4}-[0-9]{2}-[0-9]{2})\s+at\s+([0-9]{1,2}:[0-9]{2})\s+in\s+(.+)$",
            re.IGNORECASE,
        ),
        "arg_keys": ["date", "time", "meeting_room"],
        "arg_types": [str, str, str],
    },
    # Expense Reimbursement:
    # "Show my expense balance for employee 10056."
    {
        "name": "get_expense_balance",
        "pattern": re.compile(r"\bexpense balance for employee\s+(\d+)\b", re.IGNORECASE),
        "arg_keys": ["employee_id"],
        "arg_types": [int],
    },
    # Performance Bonus Calculation:
    # "Calculate performance bonus for employee 10056 for 2025."
    {
        "name": "calculate_performance_bonus",
        "pattern": re.compile(
            r"\bperformance bonus for employee\s+(\d+)\s+for\s+(\d{4})\b", re.IGNORECASE
        ),
        "arg_keys": ["employee_id", "current_year"],
        "arg_types": [int, int],
    },
    # Office Issue Reporting:
    # "Report office issue 45321 for the Facilities department."
    {
        "name": "report_office_issue",
        "pattern": re.compile(
            r"\breport (?:an |the )?office issue\s+(\d+)\s+for the\s+(.+?)\s+department\b",
            re.IGNORECASE,
        ),
        "arg_keys": ["issue_code", "department"],
        "arg_types": [int, str],
    },
]


@app.get("/execute")
def execute(q: Optional[str] = Query(None, description="templated question text")):
    if not q:
        raise HTTPException(status_code=400, detail="Missing query parameter q")

    text = q.strip()
    # Try each pattern in order
    for p in PATTERNS:
        m = p["pattern"].search(text)
        if m:
            # Extract groups
            groups = m.groups()
            if len(groups) != len(p["arg_keys"]):
                # Unexpected but handle gracefully
                raise HTTPException(status_code=500, detail="Parsing error: group count mismatch")

            # Build ordered args per function signature order
            ordered = OrderedDict()
            for key, typ, val in zip(p["arg_keys"], p["arg_types"], groups):
                # strip whitespace for string types
                if typ is int:
                    try:
                        ordered[key] = int(val)
                    except ValueError:
                        raise HTTPException(status_code=400, detail=f"Invalid integer for {key}")
                else:
                    ordered[key] = val.strip()

            return build_response(p["name"], ordered)

    # If nothing matched, try some relaxed/fuzzy alternatives (optional)
    # Quick fallback: ticket status alternate phrasing
    fallback_ticket = re.search(r"ticket\s+(\d+)", text, re.IGNORECASE)
    if fallback_ticket:
        ticket_id = int(fallback_ticket.group(1))
        return build_response("get_ticket_status", OrderedDict([("ticket_id", ticket_id)]))

    # If still no match → return 400 with helpful message
    raise HTTPException(
        status_code=400,
        detail="Could not map query to any pre-defined function. Make sure the question follows one of the templated formats.",
    )
