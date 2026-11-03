"""U8 Process Payment - MOCK of the external Payment System.   OWNER: Member 1

Provides an in-memory ledger, mock transaction generation, deposit authorization,
rental fee settlement, deposit refunds, and configurable failure modes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional


class PaymentError(Exception):
    """Raised when payment authorization, charge, or refund fails."""
    pass


class PaymentDeclined(PaymentError):
    """Raised when payment is declined (insufficient balance, card expired, etc.)."""
    pass


_ledger: Dict[str, dict] = {}
# Accounts or flags configured to fail payments during tests or demos
_declined_users: set[str] = {"PAY_FAIL", "user_fail_pay"}
_force_failure: bool = False


def reset_ledger() -> None:
    """Helper for testing: clear transactions and reset failure flags."""
    global _force_failure
    _ledger.clear()
    _force_failure = False


def set_force_failure(enable: bool) -> None:
    """Toggle simulated payment failure for exception flow demo."""
    global _force_failure
    _force_failure = enable


def authorize_deposit(user_id: str, amount: float = 50000.0) -> dict:
    """Hold a security deposit. Returns {'transaction_id', 'status': 'authorized', 'amount': amount}.
    Raises PaymentDeclined if payment fails.
    """
    if _force_failure or user_id in _declined_users or user_id.endswith("_fail_pay"):
        raise PaymentDeclined("Payment declined: Insufficient funds or payment gateway error (U8)")

    if amount < 0:
        raise ValueError("Deposit amount cannot be negative")

    tx_id = f"TX-DEP-{uuid.uuid4().hex[:8]}"
    entry = {
        "transaction_id": tx_id,
        "user_id": user_id,
        "type": "deposit",
        "amount": float(amount),
        "status": "authorized",
        "captured_amount": 0.0,
        "refunded_amount": 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _ledger[tx_id] = entry
    return {"transaction_id": tx_id, "status": "authorized", "amount": float(amount)}


def charge_trip_fee(user_id: str, transaction_id: Optional[str], amount: float) -> dict:
    """Capture rental fee from the held deposit, then refund any remaining balance.
    If no prior deposit transaction is given, charge directly.
    """
    if _force_failure or user_id in _declined_users or user_id.endswith("_fail_pay"):
        raise PaymentDeclined("Payment declined: Failed to settle trip fee")

    amount = max(0.0, float(amount))
    if transaction_id and transaction_id in _ledger:
        tx = _ledger[transaction_id]
        deposit_amount = tx["amount"]
        captured = min(deposit_amount, amount)
        refund_amount = max(0.0, deposit_amount - captured)
        tx["captured_amount"] = captured
        tx["refunded_amount"] = refund_amount
        tx["status"] = "settled"
        return {
            "transaction_id": transaction_id,
            "fee_charged": amount,
            "deposit_refunded": refund_amount,
            "status": "settled",
        }

    # Direct charge if no deposit held
    direct_tx_id = f"TX-FEE-{uuid.uuid4().hex[:8]}"
    entry = {
        "transaction_id": direct_tx_id,
        "user_id": user_id,
        "type": "trip_fee",
        "amount": amount,
        "status": "settled",
        "captured_amount": amount,
        "refunded_amount": 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _ledger[direct_tx_id] = entry
    return {
        "transaction_id": direct_tx_id,
        "fee_charged": amount,
        "deposit_refunded": 0.0,
        "status": "settled",
    }


def refund(transaction_id: str) -> dict:
    """Release/refund deposit (used by U4 cancel and Member 3 UC-OP07)."""
    if transaction_id in _ledger:
        tx = _ledger[transaction_id]
        refundable = tx["amount"] - tx["captured_amount"]
        tx["refunded_amount"] = refundable
        tx["status"] = "refunded"
        return {"transaction_id": transaction_id, "status": "refunded", "amount": refundable}

    return {"transaction_id": transaction_id, "status": "refunded", "amount": 0.0}


def get_transaction(transaction_id: str) -> Optional[dict]:
    return _ledger.get(transaction_id)


def list_transactions_by_user(user_id: str) -> List[dict]:
    return [tx for tx in _ledger.values() if tx.get("user_id") == user_id]
