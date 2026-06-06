import json
import os
import re
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen


STATE_FILE = Path(os.environ.get("STATE_FILE", "amazon-review-monitor-state.json"))
DEFAULT_ALERT_TO = "3326690363@qq.com,1336155698@qq.com"
ALERT_TO = os.environ.get("ALERT_TO", DEFAULT_ALERT_TO)
NO_CHANGE_HOURS = int(os.environ.get("NO_CHANGE_HOURS", "6"))

DEFAULT_PRODUCTS = [
    {
        "asin": "B0GY718M87",
        "url": "https://www.amazon.com/dp/B0GY718M87?th=1",
    },
    {
        "asin": "B0H2Y1FLSY",
        "url": "https://www.amazon.com/dp/B0H2Y1FLSY",
    },
    {
        "asin": "B0GWSM5C31",
        "url": "https://www.amazon.com/dp/B0GWSM5C31",
    },
    {
        "asin": "B0G43LKJDS",
        "url": "https://www.amazon.com/dp/B0G43LKJDS?th=1",
    },
]


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


def parse_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def same_rating(left, right) -> bool:
    return str(left or "") == str(right or "")


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


def detect_blocked_page(html: str) -> bool:
    text = strip_tags(html[:20000]).lower()
    return (
        "enter the characters you see below" in text
        or "robot check" in text
        or "sorry, we just need to make sure you're not a robot" in text
    )


def parse_product_reviews(html: str, asin: str):
    if detect_blocked_page(html):
        raise ValueError("Amazon returned a robot-check page.")

    title_match = re.search(
        r'<span[^>]*id="productTitle"[^>]*>([\s\S]*?)</span>',
        html,
        flags=re.I,
    )
    title = strip_tags(title_match.group(1)) if title_match else None

    escaped_asin = re.escape(asin)
    block_match = re.search(
        rf'<div[^>]+id="averageCustomerReviews"[^>]+data-asin="{escaped_asin}"[\s\S]{{0,8000}}',
        html,
        flags=re.I,
    )
    if not block_match:
        block_match = re.search(
            rf'id="averageCustomerReviews"[\s\S]{{0,1800}}data-csa-c-asin="{escaped_asin}"[\s\S]{{0,8000}}',
            html,
            flags=re.I,
        )

    if not block_match:
        if title:
            return {
                "title": title,
                "rating": None,
                "reviewCount": 0,
                "note": "No visible Amazon review widget; treated as 0 ratings.",
            }
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

    if review_count is None and title:
        review_count = 0

    if review_count is None:
        raise ValueError("Could not parse review/rating count from the main review block.")

    return {
        "title": title,
        "rating": rating,
        "reviewCount": review_count,
        "note": None,
    }


def read_state():
    if not STATE_FILE.exists():
        return {"products": []}

    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if "products" in state:
        return state

    if "asin" in state:
        return {
            "products": [
                {
                    "asin": state.get("asin"),
                    "url": state.get("url"),
                    "rating": state.get("rating"),
                    "reviewCount": state.get("reviewCount"),
                    "checkedAt": state.get("checkedAt"),
                }
            ]
        }

    return {"products": []}


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

    recipients = [
        item.strip()
        for item in re.split(r"[,;]", f"{ALERT_TO},{DEFAULT_ALERT_TO}")
        if item.strip()
    ]
    recipients = list(dict.fromkeys(recipients))
    if not recipients:
        raise RuntimeError("ALERT_TO must include at least one recipient email address.")

    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = alert_from
    message["To"] = ", ".join(recipients)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(alert_from, recipients, message.as_string())


def change_lines(change):
    delta = change["newCount"] - change["oldCount"]
    sign = "+" if delta > 0 else ""
    return [
        f"ASIN: {change['asin']}",
        f"Product URL: {change['url']}",
        f"Old rating: {change.get('oldRating') or 'N/A'}",
        f"New rating: {change.get('newRating') or 'N/A'}",
        f"Old rating/review count: {change['oldCount']}",
        f"New rating/review count: {change['newCount']}",
        f"Count change: {sign}{delta}",
    ]


def no_change_lines(item):
    return [
        f"ASIN: {item['asin']}",
        f"Product URL: {item['url']}",
        f"Rating: {item.get('rating') or 'N/A'}",
        f"Rating/review count: {item['reviewCount']}",
        f"No-change window: {NO_CHANGE_HOURS} hours",
    ]


def main():
    now = datetime.now(timezone.utc)
    checked_at = now.isoformat(timespec="seconds")
    state = read_state()
    previous_by_asin = {item.get("asin"): item for item in state.get("products", [])}
    products = state.get("products") or DEFAULT_PRODUCTS

    seen = {item.get("asin") for item in products}
    for product in DEFAULT_PRODUCTS:
        if product["asin"] not in seen:
            products.append(product)

    updated_products = []
    changes = []
    no_change_alerts = []
    failures = []

    for product in products:
        asin = product["asin"]
        url = product["url"]
        previous = previous_by_asin.get(asin, product)

        try:
            html = fetch_html(url)
            current = parse_product_reviews(html, asin)
        except Exception as exc:
            failures.append({"asin": asin, "url": url, "error": str(exc)})
            updated_products.append(previous)
            print(f"{asin}: check failed, keeping previous state. {exc}")
            continue

        old_count = previous.get("reviewCount")
        old_rating = previous.get("rating")
        new_count = int(current["reviewCount"])
        new_rating = current.get("rating")

        has_previous = old_count is not None
        rating_changed = has_previous and not same_rating(old_rating, new_rating)
        count_changed = has_previous and int(old_count) != new_count
        changed = rating_changed or count_changed

        unchanged_since = previous.get("unchangedSince") or previous.get("checkedAt") or checked_at
        last_no_change_alert_at = previous.get("lastNoChangeAlertAt")

        if changed:
            changes.append(
                {
                    "asin": asin,
                    "url": url,
                    "oldCount": int(old_count),
                    "newCount": new_count,
                    "oldRating": old_rating,
                    "newRating": new_rating,
                }
            )
            unchanged_since = checked_at
            last_no_change_alert_at = None
        elif has_previous:
            unchanged_dt = parse_time(unchanged_since) or now
            last_alert_dt = parse_time(last_no_change_alert_at)
            enough_no_change_time = now - unchanged_dt >= timedelta(hours=NO_CHANGE_HOURS)
            enough_since_last_alert = (
                last_alert_dt is None
                or now - last_alert_dt >= timedelta(hours=NO_CHANGE_HOURS)
            )
            if enough_no_change_time and enough_since_last_alert:
                no_change_alerts.append(
                    {
                        "asin": asin,
                        "url": url,
                        "rating": new_rating,
                        "reviewCount": new_count,
                    }
                )
                unchanged_since = checked_at
                last_no_change_alert_at = checked_at

        updated_product = {
            "asin": asin,
            "url": url,
            "title": current.get("title") or previous.get("title"),
            "rating": new_rating,
            "reviewCount": new_count,
            "checkedAt": checked_at,
            "unchangedSince": unchanged_since,
            "lastNoChangeAlertAt": last_no_change_alert_at,
            "note": current.get("note"),
        }
        updated_products.append(updated_product)
        print(f"{asin}: rating={new_rating or 'none'}, reviewCount={new_count}")

    email_sections = []
    subject_parts = []

    if changes:
        subject_parts.append(f"{len(changes)} changed")
        email_sections.append("Rating or rating/review count changed:")
        for change in changes:
            email_sections.append("\n".join(change_lines(change)))

    if no_change_alerts:
        subject_parts.append(f"{len(no_change_alerts)} unchanged for {NO_CHANGE_HOURS}h")
        email_sections.append(f"No rating and count changes for {NO_CHANGE_HOURS} hours:")
        for item in no_change_alerts:
            email_sections.append("\n".join(no_change_lines(item)))

    if email_sections:
        subject = "Amazon monitor alert - " + ", ".join(subject_parts)
        body = "\n\n---\n\n".join(email_sections)
        body += f"\n\nCheck time (UTC): {checked_at}"
        if failures:
            body += "\n\nThe following products failed this check and kept their previous baseline:"
            for failure in failures:
                body += f"\n- {failure['asin']}: {failure['error']}"
        send_email(subject, body)
        print(f"Alert sent to {ALERT_TO}: {', '.join(subject_parts)}.")
    else:
        print("No changes and no no-change alert due yet.")

    write_state(
        {
            "checkedAt": checked_at,
            "noChangeAlertHours": NO_CHANGE_HOURS,
            "products": updated_products,
        }
    )

    if failures:
        print(f"{len(failures)} product(s) failed to parse; previous state was preserved.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Monitor failed: {exc}", file=sys.stderr)
        sys.exit(1)
