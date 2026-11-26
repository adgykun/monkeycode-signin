#!/usr/bin/env python3
"""MonkeyCode Daily - multi-account daily check-in with server-side confirmation."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import requests

VERSION = "1.0.0"
DEFAULT_TIMEOUT = 20
MAX_HASHES = 8_000_000
MAX_CHALLENGE_MS = 600_000
MAX_SESSION_LENGTH = 8192

ORIGINS = {
    "cn": "https://monkeycode-ai.com",
    "intl": "https://monkeycode-ai.net",
}

PROVIDER_LABELS = {
    "cn": "MonkeyCode 国内版",
    "intl": "MonkeyCode 国际版",
}

CHECKIN_PATH = "/api/v1/users/wallet/checkin"
CHALLENGE_PATH = "/api/v1/public/captcha/challenge"
REDEEM_PATH = "/api/v1/public/captcha/redeem"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_SECRET_RE = re.compile(
    r"(?i)(monkeycode_ai_session|authorization|cookie|token)"
    r"(\s*[:=]\s*)([^\s;,]+)"
)


class MonkeyError(Exception):
    """Base error for a single account operation."""


class NetworkError(MonkeyError):
    """Transport or timeout error."""


class ProtocolError(MonkeyError):
    """The server returned an unexpected shape."""


class ApiError(MonkeyError):
    """The server rejected a request."""

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


@dataclass(frozen=True)
class Account:
    provider: str
    label: str
    cookie: str
    origin: str


@dataclass
class AccountResult:
    account: Account
    ok: bool
    outcome: str
    message: str
    detail: Dict[str, Any] = field(default_factory=dict)


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (LookupError, ValueError):
            pass


def _sanitize(text: Any, limit: int = 240) -> str:
    value = str(text).replace("\r", " ").replace("\n", " ").strip()
    value = _SECRET_RE.sub(r"\1\2[redacted]", value)
    return value[:limit]


def _split_entries(raw: str) -> List[str]:
    if not raw:
        return []
    entries = re.split(r"[\r\n&]+", raw)
    return [entry.strip() for entry in entries if entry.strip()]


def _normalize_cookie(secret: str) -> str:
    value = secret.strip()
    if value.lower().startswith("cookie:"):
        value = value[7:].strip()
    if not value:
        raise ValueError("empty session")
    if len(value) > MAX_SESSION_LENGTH:
        raise ValueError("session is too long")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("session contains control characters")
    if "monkeycode_ai_session=" not in value:
        value = "monkeycode_ai_session=" + value
    return value


def parse_accounts(raw: str, provider: str, default_label: str) -> List[Account]:
    """Parse newline/& separated accounts.

    Supported forms:
      session
      label|session
      label|monkeycode_ai_session=...; other=...
    """

    if provider not in ORIGINS:
        raise ValueError("unknown provider")
    accounts: List[Account] = []
    for index, entry in enumerate(_split_entries(raw), 1):
        if entry.startswith("#"):
            continue
        label = f"{default_label}-{index}"
        secret = entry
        if "|" in entry:
            candidate_label, candidate_secret = entry.split("|", 1)
            if candidate_label.strip() and candidate_secret.strip():
                label = candidate_label.strip()
                secret = candidate_secret.strip()
        try:
            cookie = _normalize_cookie(secret)
        except ValueError as exc:
            raise ValueError(f"{label}: {exc}") from exc
        accounts.append(
            Account(
                provider=provider,
                label=label,
                cookie=cookie,
                origin=ORIGINS[provider],
            )
        )
    return accounts


def load_accounts() -> List[Account]:
    accounts: List[Account] = []
    cn = _env("MONKEYCODE_CN_TOKENS") or _env("MONKEYCODE_CN_TOKEN")
    intl = _env("MONKEYCODE_INTL_TOKENS") or _env("MONKEYCODE_INTL_TOKEN")
    if cn:
        accounts.extend(parse_accounts(cn, "cn", "CN"))
    if intl:
        accounts.extend(parse_accounts(intl, "intl", "INTL"))
    return accounts


def make_session(account: Account) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": account.origin,
            "Referer": account.origin + "/console/",
            "Cookie": account.cookie,
        }
    )
    return session


def _payload_message(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("message", "msg", "error", "description", "desc"):
            value = payload.get(key)
            if value:
                return _sanitize(value)
    return ""


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    body: Optional[Dict[str, Any]] = None,
    envelope: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> Any:
    try:
        response = session.request(method, url, json=body, timeout=timeout)
    except requests.RequestException as exc:
        raise NetworkError(_sanitize(f"网络请求失败：{exc}")) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ProtocolError(_sanitize(f"服务端返回非 JSON（HTTP {response.status_code}）")) from exc

    if not 200 <= response.status_code < 300:
        message = _payload_message(payload) or "服务端拒绝请求"
        raise ApiError(
            _sanitize(f"HTTP {response.status_code}：{message}"),
            status=response.status_code,
            code=_as_int(payload.get("code")) if isinstance(payload, dict) else None,
        )

    if envelope:
        if not isinstance(payload, dict):
            raise ProtocolError("服务端信封不是对象")
        code = _as_int(payload.get("code"))
        if code != 0:
            raise ApiError(
                _sanitize(f"业务错误 code={code}：{_payload_message(payload) or '未返回说明'}"),
                status=response.status_code,
                code=code,
            )
        if "data" not in payload:
            raise ProtocolError("服务端信封缺少 data")
        return payload["data"]

    return payload


def _as_int(value: Any) -> Optional[int]:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _required_int(value: Any, name: str, low: int, high: int) -> int:
    number = _as_int(value)
    if number is None or number < low or number > high:
        raise ProtocolError(f"验证字段 {name} 无效")
    return number


def _prng(seed: str, size: int) -> str:
    """Match the 32-bit FNV-1a + xorshift generator used by the Cap host."""

    state = 2_166_136_261
    for byte in seed.encode("utf-8"):
        state = ((state ^ byte) * 16_777_619) & 0xFFFFFFFF
    output: List[str] = []
    while sum(len(part) for part in output) < size:
        state = (state ^ (state << 13)) & 0xFFFFFFFF
        state ^= state >> 17
        state = (state ^ (state << 5)) & 0xFFFFFFFF
        output.append(f"{state:08x}")
    return "".join(output)[:size]


def _target_nibbles(target: str) -> List[int]:
    try:
        return [int(char, 16) for char in target]
    except ValueError as exc:
        raise ProtocolError("Cap target 不是十六进制") from exc


def solve_cap(
    challenge: Any,
    *,
    now: Optional[float] = None,
    max_hashes: int = MAX_HASHES,
) -> List[int]:
    """Solve the challenge without sending anything to the server."""

    if not isinstance(challenge, dict):
        raise ProtocolError("Cap challenge 不是对象")
    inner = challenge.get("challenge")
    if not isinstance(inner, dict):
        raise ProtocolError("Cap challenge 缺少 challenge 字段")

    count = _required_int(inner.get("c"), "c", 1, 100)
    size = _required_int(inner.get("s"), "s", 1, 64)
    difficulty = _required_int(inner.get("d"), "d", 1, 4)

    token = challenge.get("token")
    if not isinstance(token, str) or not token or len(token) > 256:
        raise ProtocolError("Cap token 无效")
    if any(char not in "0123456789abcdefABCDEF" for char in token):
        raise ProtocolError("Cap token 不是十六进制")

    expires = _as_int(challenge.get("expires"))
    if expires is None:
        raise ProtocolError("Cap expires 无效")
    now_seconds = time.time() if now is None else now
    expires_ms = expires
    if expires_ms < 100_000_000_000:
        expires_ms *= 1000
    lifetime_ms = expires_ms - int(now_seconds * 1000)
    if lifetime_ms <= 0 or lifetime_ms > MAX_CHALLENGE_MS:
        raise ProtocolError("Cap challenge 已过期或有效期异常")

    deadline = time.monotonic() + min(lifetime_ms, 60_000) / 1000.0
    total_hashes = 0
    solutions: List[int] = []
    for index in range(1, count + 1):
        seed = f"{token}{index}"
        salt = _prng(seed, size)
        target = _target_nibbles(_prng(seed + "d", difficulty))
        solution: Optional[int] = None
        for nonce in range(4_000_000):
            total_hashes += 1
            if total_hashes > max_hashes:
                raise ProtocolError("Cap 计算超过本次预算")
            if total_hashes % 4096 == 1 and time.monotonic() >= deadline:
                raise ProtocolError("Cap 计算超时")
            digest = hashlib.sha256((salt + str(nonce)).encode("utf-8")).digest()
            if all(
                (
                    (digest[position // 2] >> 4)
                    if position % 2 == 0
                    else (digest[position // 2] & 0x0F)
                )
                == expected
                for position, expected in enumerate(target)
            ):
                solution = nonce
                break
        if solution is None:
            raise ProtocolError("Cap 未找到有效解")
        solutions.append(solution)
    return solutions


def get_status(session: requests.Session, account: Account) -> Dict[str, Any]:
    data = request_json(
        session,
        "GET",
        account.origin + CHECKIN_PATH,
        envelope=True,
    )
    if not isinstance(data, dict) or not isinstance(data.get("checked_in"), bool):
        raise ProtocolError("签到状态缺少布尔字段 checked_in")
    return data


def get_challenge(session: requests.Session, account: Account) -> Dict[str, Any]:
    data = request_json(
        session,
        "POST",
        account.origin + CHALLENGE_PATH,
        body={},
        envelope=False,
    )
    if not isinstance(data, dict):
        raise ProtocolError("Cap challenge 不是对象")
    return data


def redeem_challenge(
    session: requests.Session,
    account: Account,
    token: str,
    solutions: Sequence[int],
) -> str:
    data = request_json(
        session,
        "POST",
        account.origin + REDEEM_PATH,
        body={"token": token, "solutions": list(solutions)},
        envelope=False,
    )
    if not isinstance(data, dict) or data.get("success") is not True:
        raise ProtocolError("Cap redeem 未返回 success=true")
    redeemed_token = data.get("token")
    if not isinstance(redeemed_token, str) or not redeemed_token:
        raise ProtocolError("Cap redeem 未返回有效 token")
    if len(redeemed_token) > 256:
        raise ProtocolError("Cap redeem token 过长")
    return redeemed_token


def submit_checkin(
    session: requests.Session,
    account: Account,
    captcha_token: str,
) -> Any:
    return request_json(
        session,
        "POST",
        account.origin + CHECKIN_PATH,
        body={"captcha_token": captcha_token},
        envelope=True,
    )


def _status_view(status: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only non-secret status fields for logs and tests."""

    allowed = (
        "checked_in",
        "checked_in_at",
        "checkin_at",
        "next_checkin_at",
        "next_checkin",
        "streak",
        "continuous_days",
        "reward",
        "points",
    )
    return {key: status[key] for key in allowed if key in status}


def run_account(
    account: Account,
    *,
    session: Optional[requests.Session] = None,
    now: Optional[float] = None,
) -> AccountResult:
    owns_session = session is None
    session = session or make_session(account)
    try:
        print(f"[{account.label}] 读取签到状态")
        before = get_status(session, account)
        if before["checked_in"]:
            return AccountResult(
                account=account,
                ok=True,
                outcome="done",
                message="服务端确认今天已经签到，未重复提交",
                detail={"before": _status_view(before)},
            )

        print(f"[{account.label}] 领取 Cap challenge")
        challenge = get_challenge(session, account)
        solutions = solve_cap(challenge, now=now)
        print(f"[{account.label}] Cap 已解出 {len(solutions)} 项，提交 redeem")
        redeemed_token = redeem_challenge(
            session,
            account,
            str(challenge["token"]),
            solutions,
        )

        submit_error: Optional[MonkeyError] = None
        print(f"[{account.label}] 提交每日签到")
        try:
            submit_checkin(session, account, redeemed_token)
        except MonkeyError as exc:
            submit_error = exc

        print(f"[{account.label}] 回读服务端签到状态")
        after = get_status(session, account)
        if after["checked_in"]:
            note = "服务端已确认签到"
            if submit_error:
                note += "（提交回执异常，但回读确认成功）"
            return AccountResult(
                account=account,
                ok=True,
                outcome="claimed",
                message=note,
                detail={
                    "before": _status_view(before),
                    "after": _status_view(after),
                    "challenge_count": len(solutions),
                },
            )
        if submit_error:
            raise submit_error
        return AccountResult(
            account=account,
            ok=False,
            outcome="failed",
            message="签到提交已返回，但服务端回读仍为未签到",
            detail={
                "before": _status_view(before),
                "after": _status_view(after),
                "challenge_count": len(solutions),
            },
        )
    finally:
        if owns_session:
            session.close()


def format_summary(results: Sequence[AccountResult]) -> str:
    lines = [
        f"🐒 MonkeyCode Daily v{VERSION}",
        f"账号数: {len(results)}",
    ]
    ok_count = sum(1 for result in results if result.ok)
    for result in results:
        icon = "✅" if result.ok else "❌"
        lines.append(
            f"{icon} {result.account.label} · {PROVIDER_LABELS[result.account.provider]} · "
            f"{result.outcome} · {result.message}"
        )
        if result.detail:
            after = result.detail.get("after") or result.detail.get("before")
            if isinstance(after, dict):
                safe = {
                    key: value
                    for key, value in after.items()
                    if key in ("checked_in", "streak", "continuous_days", "reward", "points")
                }
                if safe:
                    lines.append("   " + json.dumps(safe, ensure_ascii=False, sort_keys=True))
    lines.append(f"结果: {ok_count}/{len(results)} 成功")
    return "\n".join(lines)


def _notify_enabled(results: Sequence[AccountResult]) -> bool:
    mode = _env("MONKEYCODE_NOTIFY").lower()
    if mode in ("0", "off", "false", "none"):
        return False
    if mode in ("fail", "failure", "failed"):
        return any(not result.ok for result in results)
    return True


def _post_notification(url: str, *, ok_codes: Sequence[int] = (0,), **kwargs: Any) -> None:
    try:
        response = requests.post(url, timeout=DEFAULT_TIMEOUT, **kwargs)
        if response.status_code >= 400:
            print(f"⚠️ 推送失败 HTTP {response.status_code}", file=sys.stderr)
            return
        # 飞书等渠道失败时也返回 HTTP 200，需检查 body 里的业务码
        try:
            payload = response.json()
        except ValueError:
            return
        if isinstance(payload, dict):
            for key in ("code", "StatusCode", "errcode"):
                if key in payload:
                    code = _as_int(payload.get(key))
                    if code is not None and code not in ok_codes:
                        msg = payload.get("msg") or payload.get("StatusMessage") or payload.get("errmsg")
                        print(f"⚠️ 推送业务失败 code={code} msg={msg}", file=sys.stderr)
                    break
    except requests.RequestException as exc:
        print(f"⚠️ 推送异常：{_sanitize(exc)}", file=sys.stderr)


def send_notification(text: str, results: Sequence[AccountResult]) -> None:
    if not _notify_enabled(results):
        return
    title = "MonkeyCode Daily 签到报告"
    pushplus = _env("PUSHPLUS_TOKEN")
    if pushplus:
        _post_notification(
            "https://www.pushplus.plus/send",
            json={"token": pushplus, "title": title, "content": text, "template": "markdown"},
        )
    bark = _env("BARK_URL")
    if bark:
        _post_notification(bark.rstrip("/"), json={"title": title, "body": text})
    serverchan = _env("SERVERCHAN_SENDKEY")
    if serverchan:
        _post_notification(
            f"https://sctapi.ftqq.com/{serverchan}.send",
            data={"title": title, "desp": text},
        )
    wxpusher = _env("WXPUSHER_APP_TOKEN")
    wx_uids = [item.strip() for item in re.split(r"[,;]", _env("WXPUSHER_UID")) if item.strip()]
    if wxpusher and wx_uids:
        _post_notification(
            "https://wxpusher.zjiecode.com/api/send/message",
            json={
                "appToken": wxpusher,
                "content": text,
                "summary": title,
                "contentType": 1,
                "uids": wx_uids,
            },
        )
    wecom = _env("WECOM_WEBHOOK")
    if wecom:
        _post_notification(
            wecom,
            json={"msgtype": "markdown", "markdown": {"content": text}},
        )
    feishu = _env("FEISHU_WEBHOOK")
    if feishu:
        ok_count = sum(1 for result in results if result.ok)
        total = len(results)
        if ok_count == total and total:
            title = f"✅ MonkeyCode Daily · {ok_count}/{total} 成功"
        elif ok_count:
            title = f"⚠️ MonkeyCode Daily · {ok_count}/{total} 成功"
        else:
            title = f"❌ MonkeyCode Daily · 0/{total} 成功"
        content = [
            [{"tag": "text", "text": line}]
            for line in text.splitlines()
            if line.strip()
        ]
        _post_notification(
            feishu,
            json={
                "msg_type": "post",
                "content": {"post": {"zh_cn": {"title": title, "content": content}}},
            },
        )
    dingtalk = _env("DINGTALK_WEBHOOK")
    if dingtalk:
        secret = _env("DINGTALK_SECRET")
        url = dingtalk
        if secret:
            timestamp = str(int(time.time() * 1000))
            string_to_sign = f"{timestamp}\n{secret}"
            sign = base64.b64encode(
                hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha256).digest()
            ).decode()
            separator = "&" if "?" in url else "?"
            url += f"{separator}timestamp={timestamp}&sign={urllib.parse.quote(sign)}"
        _post_notification(
            url,
            json={"msgtype": "markdown", "markdown": {"title": title, "text": text}},
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MonkeyCode multi-account daily check-in")
    parser.add_argument("--only", type=int, default=0, help="only run the 1-based account index")
    parser.add_argument(
        "--no-notify", action="store_true", help="disable notifications for this run"
    )
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)
    try:
        accounts = load_accounts()
    except ValueError as exc:
        print(f"❌ 账号配置错误：{_sanitize(exc)}", file=sys.stderr)
        return 2
    if args.only:
        if args.only < 1 or args.only > len(accounts):
            print(f"❌ --only 超出范围：{args.only}", file=sys.stderr)
            return 2
        accounts = [accounts[args.only - 1]]
    if not accounts:
        print(
            "❌ 未配置 MONKEYCODE_CN_TOKENS 或 MONKEYCODE_INTL_TOKENS",
            file=sys.stderr,
        )
        return 2

    results: List[AccountResult] = []
    for account in accounts:
        try:
            results.append(run_account(account))
        except MonkeyError as exc:
            results.append(
                AccountResult(
                    account=account,
                    ok=False,
                    outcome="failed",
                    message=_sanitize(exc),
                )
            )
        except Exception as exc:  # keep one account from aborting the batch
            results.append(
                AccountResult(
                    account=account,
                    ok=False,
                    outcome="failed",
                    message=_sanitize(f"未分类异常：{exc}"),
                )
            )

    summary = format_summary(results)
    print("\n" + summary)
    if not args.no_notify:
        send_notification(summary, results)
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
