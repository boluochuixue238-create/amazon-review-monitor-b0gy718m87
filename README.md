# Amazon Review Monitor for GitHub Actions

This repository has two monitors:

1. **Amazon Review Monitor** checks the regular ASIN list every 2 hours and emails only when the old alert rules are met, including rating/count changes and 6-hour no-change alerts.
2. **Amazon Primary ASIN Hourly Monitor** checks B0GHQMRWQ8 every hour and sends a status report every run to 3326690363@qq.com only.

## Primary hourly monitor

| ASIN | Product URL | Recipient | Schedule |
| --- | --- | --- | --- |
| B0GHQMRWQ8 | https://www.amazon.com/dp/B0GHQMRWQ8 | 3326690363@qq.com | every hour |

## Regular monitor

Regular alert recipients: 3326690363@qq.com, 1336155698@qq.com, 784541190@qq.com

Regular monitored ASINs:

- B0GY718M87: https://www.amazon.com/dp/B0GY718M87?th=1
- B0H2Y1FLSY: https://www.amazon.com/dp/B0H2Y1FLSY
- B0GWSM5C31: https://www.amazon.com/dp/B0GWSM5C31
- B0G43LKJDS: https://www.amazon.com/dp/B0G43LKJDS?th=1
- B0GHRJT3K7: https://www.amazon.com/dp/B0GHRJT3K7
- B0GFMHNT24: https://www.amazon.com/dp/B0GFMHNT24
- B0GCZ11B8D: https://www.amazon.com/dp/B0GCZ11B8D
- B0G8XNTZ6N: https://www.amazon.com/dp/B0G8XNTZ6N
- B0G8YQZ2R5: https://www.amazon.com/dp/B0G8YQZ2R5
- B0G8XVQM3H: https://www.amazon.com/dp/B0G8XVQM3H
- B0GQLRGWKD: https://www.amazon.com/dp/B0GQLRGWKD
- B0GQM2QMBG: https://www.amazon.com/dp/B0GQM2QMBG
- B0GQM5D3KF: https://www.amazon.com/dp/B0GQM5D3KF
- B0GRZ22VZX: https://www.amazon.com/dp/B0GRZ22VZX

## GitHub Secrets

Required repository secrets:

- `SMTP_USER`: the Gmail address used to send alerts
- `SMTP_PASSWORD`: Gmail app password, not the normal Gmail login password
