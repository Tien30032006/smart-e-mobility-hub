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
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlencode

import requests
from ...core.config import settings


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


def available_payment_methods() -> list[dict]:
    """Expose only providers that have the credentials needed for a real checkout."""
    return [
        {"id": "vietqr", "configured": bool(os.getenv("VIETQR_BANK_ID") and os.getenv("VIETQR_ACCOUNT_NO") and os.getenv("VIETQR_ACCOUNT_NAME"))},
        {"id": "momo", "configured": bool(os.getenv("MOMO_PARTNER_CODE") and os.getenv("MOMO_ACCESS_KEY")
                                             and os.getenv("MOMO_SECRET_KEY") and os.getenv("MOMO_PUBLIC_BASE_URL"))},
        {"id": "demo", "configured": settings.demo_mode},
    ]


def _topup_checkout_url(order_id: str, method: str, amount: int, user_id: str,
                        signature: str, qr_payload: str = "", qr_image_url: str = "") -> str:
    params = {"order_id": order_id, "method": method}
    if method == "demo":
        params.update(amount=str(amount), user_id=user_id, signature=signature)
    if qr_payload:
        params["qr"] = qr_payload
    if qr_image_url:
        params["qr_image"] = qr_image_url
    return "/app/student/mock-checkout.html?" + urlencode(params)


def _make_vietqr(order_id: str, amount: int) -> tuple[str, str, str]:
    bank_id = os.getenv("VIETQR_BANK_ID", "").strip()
    account_no = os.getenv("VIETQR_ACCOUNT_NO", "").strip()
    account_name = os.getenv("VIETQR_ACCOUNT_NAME", "").strip()
    if not (bank_id and account_no.isdigit() and account_name):
        raise PaymentError("VietQR receiver account is not configured")
    reference = "SMH" + uuid.uuid4().hex[:8].upper()
    clean_name = unicodedata.normalize("NFD", account_name).encode("ascii", "ignore").decode().upper()
    clean_name = re.sub(r"[^A-Z0-9 ]", "", clean_name).strip()
    if len(account_no) < 6 or len(account_no) > 19 or not 5 <= len(clean_name) <= 50:
        raise PaymentError("VietQR account details are invalid")
    query = urlencode({"amount": str(amount), "addInfo": reference, "accountName": clean_name})
    image_url = f"https://img.vietqr.io/image/{bank_id}-{account_no}-compact2.png?{query}"
    return reference, image_url, account_name


def _make_momo(order_id: str, amount: int, user_id: str) -> tuple[str, str]:
    partner_code = os.getenv("MOMO_PARTNER_CODE", "").strip()
    access_key = os.getenv("MOMO_ACCESS_KEY", "").strip()
    secret_key = os.getenv("MOMO_SECRET_KEY", "").strip()
    base_url = os.getenv("MOMO_PUBLIC_BASE_URL", "").strip().rstrip("/")
    api_base = os.getenv("MOMO_API_BASE", "https://test-payment.momo.vn").strip().rstrip("/")
    if not (partner_code and access_key and secret_key and base_url.startswith("https://")):
        raise PaymentError("MoMo merchant credentials and public HTTPS callback URL are not configured")
    request_id = uuid.uuid4().hex
    order_info = f"Nap vi {order_id}"
    redirect_url = f"{base_url}/app/student/wallet.html?checkout=pending&order_id={order_id}"
    ipn_url = f"{base_url}/api/payments/momo/ipn"
    extra_data = ""
    request_type = "payWithMethod"
    raw = (f"accessKey={access_key}&amount={amount}&extraData={extra_data}&ipnUrl={ipn_url}"
           f"&orderId={order_id}&orderInfo={order_info}&partnerCode={partner_code}"
           f"&redirectUrl={redirect_url}&requestId={request_id}&requestType={request_type}")
    signature = hmac.new(secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()
    payload = {"partnerCode": partner_code, "requestId": request_id, "amount": amount,
               "orderId": order_id, "orderInfo": order_info, "redirectUrl": redirect_url,
               "ipnUrl": ipn_url, "requestType": request_type, "extraData": extra_data,
               "lang": "vi", "autoCapture": True, "signature": signature}
    try:
        response = requests.post(f"{api_base}/v2/gateway/api/create", json=payload, timeout=12)
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise PaymentError("Could not create a MoMo payment request") from exc
    if result.get("resultCode") != 0 or not result.get("payUrl"):
        raise PaymentError(result.get("message") or "MoMo rejected the payment request")
    return str(result.get("qrCodeUrl") or result["payUrl"]), request_id


def create_topup_order(user_id: str, amount: int, method: str = "demo") -> dict:
    """POST /api/wallet/topup: Create a pending top-up order and return checkout pay_url."""
    if amount < 10000:
        raise ValueError("Minimum top-up amount is 10,000 VND")

    available = {item["id"] for item in available_payment_methods() if item["configured"]}
    if method not in available:
        raise ValueError("This payment method is not configured")
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    sig = compute_signature(order_id, amount, user_id)
    order = {
        "order_id": order_id,
        "user_id": user_id,
        "amount": amount,
        "status": "pending",
        "signature": sig,
        "method": method,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    qr_payload = qr_image_url = payment_ref = ""
    if method == "vietqr":
        payment_ref, qr_image_url, account_name = _make_vietqr(order_id, amount)
        order.update(payment_ref=payment_ref, account_name=account_name, qr_image_url=qr_image_url,
                     receiver_bank_id=os.getenv("VIETQR_BANK_ID", "").strip(),
                     receiver_account_no=os.getenv("VIETQR_ACCOUNT_NO", "").strip())
    elif method == "momo":
        qr_payload, request_id = _make_momo(order_id, amount, user_id)
        order.update(momo_request_id=request_id, momo_qr_payload=qr_payload)
    _orders[order_id] = order
    pay_url = _topup_checkout_url(order_id, method, amount, user_id, sig, qr_payload, qr_image_url)

    return {
        "order_id": order_id,
        "amount": amount,
        "pay_url": pay_url,
        "signature": sig,
        "method": method,
        "payment_ref": payment_ref,
        "status": "pending",
    }


def get_order_status(user_id: str, order_id: str) -> dict:
    order = _orders.get(order_id)
    if not order or order.get("user_id") != user_id:
        raise PaymentError("Payment order not found")
    return {"order_id": order_id, "status": order["status"], "method": order.get("method", "demo"),
            "amount": order["amount"], "payment_ref": order.get("payment_ref", ""),
            "qr_image_url": order.get("qr_image_url", ""), "qr_payload": order.get("momo_qr_payload", ""),
            "account_name": order.get("account_name", ""), "bank_id": order.get("receiver_bank_id", ""),
            "account_no": order.get("receiver_account_no", "")}


def process_momo_ipn(payload: dict) -> dict:
    """Verify a server-to-server MoMo IPN before changing the wallet balance."""
    secret_key, access_key = os.getenv("MOMO_SECRET_KEY", ""), os.getenv("MOMO_ACCESS_KEY", "")
    if not secret_key or not access_key:
        raise PaymentError("MoMo IPN is not configured")
    fields = ("accessKey", "amount", "extraData", "message", "orderId", "orderInfo", "orderType",
              "partnerCode", "payType", "requestId", "responseTime", "resultCode", "transId")
    raw = "&".join(f"{key}={access_key if key == 'accessKey' else payload.get(key, '')}" for key in fields)
    expected = hmac.new(secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(payload.get("signature", ""))):
        raise PaymentError("Invalid MoMo notification signature")
    order = _orders.get(str(payload.get("orderId", "")))
    if (not order or order.get("method") != "momo" or order["amount"] != int(payload.get("amount", 0))
            or order.get("momo_request_id") != payload.get("requestId")
            or order.get("status") != "pending"
            or os.getenv("MOMO_PARTNER_CODE", "") != payload.get("partnerCode")):
        raise PaymentError("MoMo notification does not match a pending order")
    success = int(payload.get("resultCode", -1)) == 0
    return process_verified_provider_result(order, success)


def process_verified_provider_result(order: dict, success: bool) -> dict:
    if order["status"] in ("completed", "failed"):
        return {"order_id": order["order_id"], "status": order["status"], "idempotent": True}
    if success:
        wallet = _wallets.get(order["user_id"])
        if not wallet:
            get_wallet(order["user_id"])
            wallet = _wallets[order["user_id"]]
        wallet["balance"] += float(order["amount"])
        wallet["updated_at"] = datetime.now(timezone.utc).isoformat()
        order["status"] = "completed"
        tx_id = f"TX-TOP-{uuid.uuid4().hex[:8]}"
        _ledger[tx_id] = {"transaction_id": tx_id, "user_id": order["user_id"], "type": "topup",
                          "amount": float(order["amount"]), "status": "completed", "order_id": order["order_id"],
                          "timestamp": datetime.now(timezone.utc).isoformat()}
    else:
        order["status"] = "failed"
    return {"order_id": order["order_id"], "status": order["status"], "idempotent": False}


def process_payment_callback(order_id: str, amount: int, user_id: str,
                             signature: str, success: bool) -> dict:
    """POST /api/payments/callback: Process payment callback with HMAC check & idempotency."""
    if not verify_signature(order_id, amount, user_id, signature):
        raise PaymentError("Invalid payment signature")

    order = _orders.get(order_id)
    if not order:
        raise PaymentError(f"Order {order_id} not found")
    if order.get("method", "demo") != "demo":
        raise PaymentError("Live payment orders can only be confirmed by the payment provider")

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
