# Issue #107: Pull and display Claude Code usage stats

## Problem

There's no visibility into Claude Code API usage (tokens, costs, requests) from within the Codehive web app. The user wants to track how much they're spending and how much capacity they're using.

## Requirements

- [ ] Pull Claude Code / Anthropic API usage data
- [ ] Display usage stats in the web app (dashboard or dedicated page)
- [ ] Show token counts, request counts, costs if available
- [ ] Historical usage over time (daily/weekly/monthly)

## Notes

- Need to determine what usage APIs are available (Anthropic API usage endpoints, billing API, etc.)
- May need to track usage locally per session/project in addition to pulling from the provider
