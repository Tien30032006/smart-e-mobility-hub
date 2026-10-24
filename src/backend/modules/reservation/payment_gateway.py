"""U8 Process Payment - MOCK of the external Payment System.   OWNER: Member 1

No real gateway is needed. Return fake transaction ids and keep an in-memory ledger.
"""
from ...core.todo import todo

OWNER = "Member 1"


def authorize_deposit(user_id: str, amount: float) -> dict:
    """Hold a security deposit. Return {'transaction_id', 'status': 'authorized'}; may fail (declined)."""
    todo(OWNER, "U8", "mock authorization + ledger entry")


def charge_trip_fee(user_id: str, transaction_id: str, amount: float) -> dict:
    todo(OWNER, "U8", "capture fee from the held deposit")


def refund(transaction_id: str) -> dict:
    todo(OWNER, "U8", "release/refund deposit (used by U4 cancel and Member 3 UC-OP07)")
