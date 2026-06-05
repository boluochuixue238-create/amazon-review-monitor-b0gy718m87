# Amazon Review Monitor for GitHub Actions

This GitHub Actions workflow checks the Amazon product below every 2 hours and emails an alert when the review/rating count changes.

- Product: https://www.amazon.com/dp/B0GY718M87?th=1
- ASIN: B0GY718M87
- Alert recipient: 3326690363@qq.com
- Current baseline: rating 3.7, review/rating count 10

## GitHub Secrets

Create these repository secrets before running the workflow:

- `SMTP_USER`: the Gmail address used to send alerts
- `SMTP_PASSWORD`: a Gmail app password, not the normal Gmail login password

For Gmail, enable 2-step verification first, then create an app password in your Google account security settings.

## Files

Place these files at the root of your GitHub repository:

- `.github/workflows/amazon-review-monitor.yml`
- `scripts/amazon_review_monitor.py`
- `amazon-review-monitor-state.json`

After the workflow is enabled, it can also be tested manually from the Actions tab with `Run workflow`.
