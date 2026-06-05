import json
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.text import MIMEText
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen


ASIN = os.environ.get("ASIN", "B0GY718M87")
PRODUCT_URL = os.environ.get("AMAZON_URL", "https://www.amazon.com/dp/B0GY718M87?th=1")
STATE_FILE = Path(os.environ.get("STATE_FILE", "amazon-review-monitor-state.json"))
ALERT_TO = os.environ.get("ALERT_TO", "3326690363@qq.com")


def strip_tags(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.I)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]*>", " ", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()


def parse_count(value: str):
    match = re.search(r"([0-9][0-9,]*)", value or "")
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_product_reviews(html: str, asin: str):
    escaped_asin = re.escape(asin)
    block_match = re.search(
        rf'<div[^>]+id="averageCustomerReviews"[^>]+data-asin="{escaped_asin}"[\s\S]{{0,6000}}',
        html,
        flags=re.I,
    )
    if not block_match:
        block_match = re.search(
            rf'id="averageCustomerReviews"[\s\S]{{0,1500}}data-csa-c-asin="{escaped_asin}"[\s\S]{{0,6000}}',
            html,
            flags=re.I,
        )
    if not block_match:
        raise ValueError(f"Could not find the main customer review block for ASIN {asin}.")

    block = block_match.group(0)
    rating_match = re.search(r'title="([0-9.]+)\s+out of 5 stars"', block, flags=re.I)
    if not rating_match:
        rating_match = re.search(r"([0-9.]+)\s+out of 5 stars", strip_tags(block), flags=re.I)
    rating = rating_match.group(1) if rating_match else None

    review_text_match = re.search(
        r'id="acrCustomerReviewText"[^>]*>([\s\S]*?)</span>',
        block,
        flags=re.I,
    )
    review_text = strip_tags(review_text_match.group(1)) if review_text_match else ""
    review_count = parse_count(review_text)

    if review_count is None:
        compact_text = strip_tags(block)
        count_match = re.search(r"\(([0-9][0-9,]*)\)", compact_text)
        review_count = parse_count(count_match.group(1)) if count_match else None

    if review_count is None:
        raise ValueError("Could not parse review/rating count from the main review block.")

    return {"rating": rating, "reviewCount": review_count}


def read_state():
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def write_state(state):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def send_email(subject: str, body: str):
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    alert_from = os.environ.get("ALERT_FROM", smtp_user or "")

    if not smtp_user or not smtp_password:
        raise RuntimeError("SMTP_USER and SMTP_PASSWORD secrets are required to send alerts.")

    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = alert_from
    message["To"] = ALERT_TO

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(alert_from, [ALERT_TO], message.as_string())


def main():
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    previous = read_state()

    html = fetch_html(PRODUCT_URL)
    current = parse_product_reviews(html, ASIN)
    previous_count = previous.get("reviewCount")
    previous_rating = previous.get("rating")

    has_baseline = previous_count is not None
    count_changed = has_baseline and current["reviewCount"] != previous_count

    if count_changed:
        delta = current["reviewCount"] - int(previous_count)
        sign = "+" if delta > 0 else ""
        subject = f"Amazon评论数量变化提醒 - {ASIN}"
        body = "\n".join(
            [
                f"ASIN: {ASIN}",
                f"商品链接: {PRODUCT_URL}",
                f"原评论/评分数量: {previous_count}",
                f"当前评论/评分数量: {current['reviewCount']}",
                f"变化: {sign}{delta}",
                f"原评分: {previous_rating or '未知'}",
                f"当前评分: {current.get('rating') or '未知'}",
                f"检查时间(UTC): {checked_at}",
            ]
        )
        send_email(subject, body)
        print(f"Alert sent to {ALERT_TO}: review count changed from {previous_count} to {current['reviewCount']}.")
    elif not has_baseline:
        print(f"Baseline created: review count is {current['reviewCount']}.")
    else:
        print(f"No review count change: still {current['reviewCount']}.")

    should_update_state = (
        not has_baseline
        or current["reviewCount"] != previous_count
        or current.get("rating") != previous_rating
    )
    if should_update_state:
        write_state(
            {
                "asin": ASIN,
                "url": PRODUCT_URL,
                "rating": current.get("rating"),
                "reviewCount": current["reviewCount"],
                "checkedAt": checked_at,
            }
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Monitor failed: {exc}", file=sys.stderr)
        sys.exit(1)
