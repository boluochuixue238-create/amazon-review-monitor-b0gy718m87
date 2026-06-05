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


STATE_FILE = Path(os.environ.get("STATE_FILE", "amazon-review-monitor-state.json"))
ALERT_TO = os.environ.get("ALERT_TO", "3326690363@qq.com")

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
        # Some Amazon pages with zero ratings render no visible star/review widget.
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

    # Backward compatibility for the original single-ASIN state file.
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

    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = alert_from
    message["To"] = ALERT_TO

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(alert_from, [ALERT_TO], message.as_string())


def product_lines(change):
    delta = change["newCount"] - change["oldCount"]
    sign = "+" if delta > 0 else ""
    return [
        f"ASIN: {change['asin']}",
        f"商品链接: {change['url']}",
        f"原评论/评分数量: {change['oldCount']}",
        f"当前评论/评分数量: {change['newCount']}",
        f"变化: {sign}{delta}",
        f"原评分: {change.get('oldRating') or '未知'}",
        f"当前评分: {change.get('newRating') or '未知'}",
    ]


def main():
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state = read_state()
    previous_by_asin = {item.get("asin"): item for item in state.get("products", [])}
    products = state.get("products") or DEFAULT_PRODUCTS

    # Keep newly configured products even if an older state file exists.
    seen = {item.get("asin") for item in products}
    for product in DEFAULT_PRODUCTS:
        if product["asin"] not in seen:
            products.append(product)

    updated_products = []
    changes = []
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
        new_count = current["reviewCount"]
        new_rating = current.get("rating")

        if old_count is not None and int(old_count) != int(new_count):
            changes.append(
                {
                    "asin": asin,
                    "url": url,
                    "oldCount": int(old_count),
                    "newCount": int(new_count),
                    "oldRating": old_rating,
                    "newRating": new_rating,
                }
            )

        updated_products.append(
            {
                "asin": asin,
                "url": url,
                "title": current.get("title") or previous.get("title"),
                "rating": new_rating,
                "reviewCount": new_count,
                "checkedAt": checked_at,
                "note": current.get("note"),
            }
        )
        print(f"{asin}: rating={new_rating or 'none'}, reviewCount={new_count}")

    if changes:
        subject = f"Amazon评论数量变化提醒 - {len(changes)}个ASIN"
        sections = []
        for change in changes:
            sections.append("\n".join(product_lines(change)))
        body = "\n\n---\n\n".join(sections)
        body += f"\n\n检查时间(UTC): {checked_at}"
        if failures:
            body += "\n\n以下商品本次检查失败，已保留旧基准："
            for failure in failures:
                body += f"\n- {failure['asin']}: {failure['error']}"
        send_email(subject, body)
        print(f"Alert sent to {ALERT_TO}: {len(changes)} product(s) changed.")
    else:
        print("No review count changes.")

    write_state(
        {
            "checkedAt": checked_at,
            "products": updated_products,
        }
    )

    if failures:
        print(f"{len(failures)} product(s) failed to parse; previous state was preserved for them.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Monitor failed: {exc}", file=sys.stderr)
        sys.exit(1)
