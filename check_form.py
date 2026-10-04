import datetime, json, os, sys
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

FORM_URL = os.environ["FORM_URL"]
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
KEYWORDS = [k.strip() for k in os.environ.get("CLOSED_KEYWORDS", "종료,참여할 수 없습니다").split(",") if k.strip()]
MENTION = os.environ.get("DISCORD_MENTION", "")
STATE_FILE = Path("state.json")
KST = datetime.timezone(datetime.timedelta(hours=9))


def now_kst():
    return datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"status": None, "fail_count": 0}


def save_state(s):
    STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(locale="ko-KR", user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"))
        try:
            r = page.goto(FORM_URL, wait_until="networkidle", timeout=45000)
            page.wait_for_timeout(3000)
            return (r.status if r else None), page.inner_text("body")
        finally:
            b.close()


def send(msg):
    requests.post(WEBHOOK_URL, json={"content": f"{MENTION} {msg}".strip(),
                                     "username": "네이버폼 감시봇"}, timeout=15).raise_for_status()


def main():
    st = load_state()
    prev = st.get("status")
    try:
        code, text = fetch()
    except Exception as e:
        code, text = None, ""
        print("[ERROR]", e)

    found = [k for k in KEYWORDS if k in text]
    cur = ("closed" if found else "open") if code == 200 and len(text.strip()) >= 30 else "unknown"
    print(f"[{now_kst()}] HTTP={code} len={len(text)} found={found} prev={prev} now={cur}")

    if cur == "unknown":
        st["fail_count"] = st.get("fail_count", 0) + 1
        if st["fail_count"] == 3:
            send(f"⚠️ 폼 페이지 확인 3회 연속 실패 (HTTP {code})\n{FORM_URL}")
        save_state(st)
        return

    st["fail_count"] = 0
    if cur == "open" and prev != "open":
        send(f"🟢 **네이버폼이 열렸습니다!** ({now_kst()})\n{FORM_URL}")
    elif cur == "closed" and prev == "open":
        send(f"🔴 네이버폼이 다시 마감되었습니다. ({now_kst()})")
    if cur != prev:
        st["status"], st["changed_at"] = cur, now_kst()
    save_state(st)


if __name__ == "__main__":
    sys.exit(main())
