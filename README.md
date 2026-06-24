# Amazon Review Monitor for GitHub Actions

This GitHub Actions workflow checks multiple Amazon products every hour and emails a status report every run, whether or not review/rating values changed.

## Products

| ASIN | Product URL | Current baseline |
| --- | --- | --- |
| B0GHQMRWQ8 | https://www.amazon.com/dp/B0GHQMRWQ8 | primary ASIN, baseline pending |
| B0GY718M87 | https://www.amazon.com/dp/B0GY718M87?th=1 | rating 4.3, review/rating count 9 |
| B0H2Y1FLSY | https://www.amazon.com/dp/B0H2Y1FLSY | no visible rating widget, treated as 0 |
| B0GWSM5C31 | https://www.amazon.com/dp/B0GWSM5C31 | rating 5.0, review/rating count 2 |
| B0G43LKJDS | https://www.amazon.com/dp/B0G43LKJDS?th=1 | rating 3.2, review/rating count 16 |
| B0GHRJT3K7 | https://www.amazon.com/dp/B0GHRJT3K7 | baseline pending |
| B0GFMHNT24 | https://www.amazon.com/dp/B0GFMHNT24 | baseline pending |
| B0GCZ11B8D | https://www.amazon.com/dp/B0GCZ11B8D | baseline pending |
| B0G8XNTZ6N | https://www.amazon.com/dp/B0G8XNTZ6N | baseline pending |
| B0G8YQZ2R5 | https://www.amazon.com/dp/B0G8YQZ2R5 | baseline pending |
| B0G8XVQM3H | https://www.amazon.com/dp/B0G8XVQM3H | baseline pending |
| B0GQLRGWKD | https://www.amazon.com/dp/B0GQLRGWKD | baseline pending |
| B0GQM2QMBG | https://www.amazon.com/dp/B0GQM2QMBG | baseline pending |
| B0GQM5D3KF | https://www.amazon.com/dp/B0GQM5D3KF | baseline pending |
| B0GRZ22VZX | https://www.amazon.com/dp/B0GRZ22VZX | baseline pending |

Alert recipients: 3326690363@qq.com, 1336155698@qq.com, 784541190@qq.com

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
