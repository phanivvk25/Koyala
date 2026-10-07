# Background Jobs

Run from cron, a scheduler or a Kubernetes CronJob, with the same environment as the API.

| Command | Schedule | What it does |
|---|---|---|
| `python -m koyala.jobs sweep-escalations` | every minute | Pages on-call once for each counsellor request not connected within 5 minutes |
| `python -m koyala.jobs send-follow-ups` | every 5 minutes | Sends due follow-up check-ins (24 h after tier 2, 12 h after tier ≥ 3); pages on-call once for tier ≥ 3 check-ins unanswered for 24 h |

Both are safe to run repeatedly: each page or check-in is sent once.

Example crontab:

```cron
* * * * *   cd /app/backend && python -m koyala.jobs sweep-escalations
*/5 * * * * cd /app/backend && python -m koyala.jobs send-follow-ups
```

**Placeholders:** paging goes to the log (`LogPager`) and push notifications to the log (`LogNotifier`) until real services are connected.

**Not yet built:** the safety protocol's daily repeat check-in for 3 days after tier ≥ 3.
