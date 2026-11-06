"""U8 Process Payment & Student Wallet - MOCK Payment Provider.   OWNER: Member 1

Provides:
- In-memory Student Wallet with 200,000 VND default balance.
- Deposit authorization and trip fee settlement integrated with student wallet.
- Top-up order generation with HMAC signature.
- Idempotent callback processing for simulated checkout (MoMo / VNPay style).
- Full audit ledger of all financial transactions.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional


class PaymentError(Exception):
    """Raised when payment authorization, charge, or refund fails."""
    pass


class PaymentDeclined(PaymentError):
    """Raised when payment is declined (insufficient balance, card expired, etc.)."""
    pass


PAYMENT_SECRET = os.getenv("PAYMENT_SECRET", "smart-e-mobility-vnu-hcm-2026-secret-key")

_wallets: Dict[str, dict] = {}
_orders: Dict[str, dict] = {}
_ledger: Dict[str, dict] = {}
_declined_users: set[str] = {"PAY_FAIL", "user_fail_pay"}
_force_failure: bool = False


def reset_ledger() -> None:
    """Helper for testing: clear all state."""
    global _force_failure
    _wallets.clear()
    _orders.clear()
    _ledger.clear()
    _force_failure = False


def set_force_failure(enable: bool) -> None:
    """Toggle simulated payment failure for exception flow demo."""
    global _force_failure
    _force_failure = enable


def get_wallet(user_id: str) -> dict:
    """Get or initialize student wallet with 200,000 VND default balance."""
    if user_id not in _wallets:
        _wallets[user_id] = {
            "user_id": user_id,
            "balance": 200000.0,
            "held_deposit": 0.0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    w = _wallets[user_id]
    return {
        "user_id": w["user_id"],
        "balance": w["balance"],
        "held_deposit": w["held_deposit"],
        "available_balance": max(0.0, w["balance"] - w["held_deposit"]),
        "currency": "VND",
        "updated_at": w["updated_at"],
    }


def compute_signature(order_id: str, amount: int, user_id: str) -> str:
    """Generate SHA256 HMAC signature for checkout security."""
    raw = f"{order_id}:{amount}:{user_id}"
    return hmac.new(PAYMENT_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()


def verify_signature(order_id: str, amount: int, user_id: str, signature: str) -> bool:
    """Validate HMAC signature."""
    expected = compute_signature(order_id, amount, user_id)
    return hmac.compare_digest(expected, signature)


def create_topup_order(user_id: str, amount: int) -> dict:
    """POST /api/wallet/topup: Create a pending top-up order and return checkout pay_url."""
    if amount < 10000:
        raise ValueError("Minimum top-up amount is 10,000 VND")

    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    sig = compute_signature(order_id, amount, user_id)

    order = {
        "order_id": order_id,
        "user_id": user_id,
        "amount": amount,
        "status": "pending",
        "signature": sig,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _orders[order_id] = order

    pay_url = (
        f"/app/student/mock-checkout.html?order_id={order_id}"
        f"&amount={amount}&user_id={user_id}&signature={sig}"
    )

    return {
        "order_id": order_id,
        "amount": amount,
        "pay_url": pay_url,
        "signature": sig,
        "status": "pending",
    }


def process_payment_callback(order_id: str, amount: int, user_id: str,
                             signature: str, success: bool) -> dict:
    """POST /api/payments/callback: Process payment callback with HMAC check & idempotency."""
    if not verify_signature(order_id, amount, user_id, signature):
        raise PaymentError("Invalid payment signature")

    order = _orders.get(order_id)
    if not order:
        raise PaymentError(f"Order {order_id} not found")

    # Idempotency: If already completed or failed, return recorded state without re-crediting
    if order["status"] in ("completed", "failed"):
        w = get_wallet(user_id)
        return {
            "order_id": order_id,
            "status": order["status"],
            "amount": amount,
            "new_balance": w["balance"],
            "idempotent": True,
        }

    if success:
        # Credit wallet
        wallet = _wallets.get(user_id)
        if not wallet:
            get_wallet(user_id)
            wallet = _wallets[user_id]

        wallet["balance"] += float(amount)
        wallet["updated_at"] = datetime.now(timezone.utc).isoformat()
        order["status"] = "completed"

        # Log into ledger
        tx_id = f"TX-TOP-{uuid.uuid4().hex[:8]}"
        _ledger[tx_id] = {
            "transaction_id": tx_id,
            "user_id": user_id,
            "type": "topup",
            "amount": float(amount),
            "status": "completed",
            "order_id": order_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return {
            "order_id": order_id,
            "status": "completed",
            "amount": amount,
            "new_balance": wallet["balance"],
            "idempotent": False,
        }
    else:
        order["status"] = "failed"
        w = get_wallet(user_id)
        return {
            "order_id": order_id,
            "status": "failed",
            "amount": amount,
            "new_balance": w["balance"],
            "idempotent": False,
        }


def authorize_deposit(user_id: str, amount: float = 50000.0) -> dict:
    """Hold a security deposit from student wallet.
    Raises PaymentDeclined if wallet balance is insufficient or failure simulated.
    """
    if _force_failure or user_id in _declined_users or user_id.endswith("_fail_pay"):
        raise PaymentDeclined("Payment declined: Insufficient funds or gateway error (U8)")

    if amount < 0:
        raise ValueError("Deposit amount cannot be negative")

    # Verify wallet has enough available balance
    w = get_wallet(user_id)
    if w["available_balance"] < amount:
        raise PaymentDeclined(
            f"Insufficient wallet balance ({w['available_balance']:,.0f} VND). "
            f"Required deposit is {amount:,.0f} VND. Please top up your wallet!"
        )

    # Hold deposit
    _wallets[user_id]["held_deposit"] += float(amount)
    _wallets[user_id]["updated_at"] = datetime.now(timezone.utc).isoformat()

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
    """Capture rental fee from wallet, release held deposit, and refund balance."""
    if _force_failure or user_id in _declined_users or user_id.endswith("_fail_pay"):
        raise PaymentDeclined("Payment declined: Failed to settle trip fee")

    amount = max(0.0, float(amount))
    wallet = _wallets.get(user_id)
    if not wallet:
        get_wallet(user_id)
        wallet = _wallets[user_id]

    deposit_amount = 50000.0
    if transaction_id and transaction_id in _ledger:
        tx = _ledger[transaction_id]
        deposit_amount = tx["amount"]
        captured = min(deposit_amount, amount)
        refund_amount = max(0.0, deposit_amount - captured)
        tx["captured_amount"] = captured
        tx["refunded_amount"] = refund_amount
        tx["status"] = "settled"

    # Deduct actual trip fee from wallet balance, release held deposit
    wallet["balance"] = max(0.0, wallet["balance"] - amount)
    wallet["held_deposit"] = max(0.0, wallet["held_deposit"] - deposit_amount)
    wallet["updated_at"] = datetime.now(timezone.utc).isoformat()

    fee_tx_id = f"TX-FEE-{uuid.uuid4().hex[:8]}"
    _ledger[fee_tx_id] = {
        "transaction_id": fee_tx_id,
        "user_id": user_id,
        "type": "trip_fee",
        "amount": amount,
        "status": "settled",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "transaction_id": transaction_id or fee_tx_id,
        "fee_charged": amount,
        "deposit_refunded": max(0.0, deposit_amount - amount),
        "status": "settled",
    }


def refund(transaction_id: str) -> dict:
    """Release/refund deposit (used by U4 cancel and Member 3 UC-OP07)."""
    if transaction_id in _ledger:
        tx = _ledger[transaction_id]
        refundable = tx["amount"] - tx["captured_amount"]
        tx["refunded_amount"] = refundable
        tx["status"] = "refunded"

        user_id = tx.get("user_id")
        if user_id and user_id in _wallets:
            _wallets[user_id]["held_deposit"] = max(0.0, _wallets[user_id]["held_deposit"] - refundable)
            _wallets[user_id]["updated_at"] = datetime.now(timezone.utc).isoformat()

        return {"transaction_id": transaction_id, "status": "refunded", "amount": refundable}

    return {"transaction_id": transaction_id, "status": "refunded", "amount": 0.0}


def get_transaction(transaction_id: str) -> Optional[dict]:
    return _ledger.get(transaction_id)


def list_transactions_by_user(user_id: str) -> List[dict]:
    txs = [tx for tx in _ledger.values() if tx.get("user_id") == user_id]
    txs.sort(key=lambda t: t.get("timestamp", ""), reverse=True)
    return txs
