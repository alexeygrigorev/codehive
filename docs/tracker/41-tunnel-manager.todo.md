# 41: Tunnel Manager and Preview Links

## Description
Implement SSH tunnel management for port forwarding and dev server previews. Provide a registry of active tunnels, lifecycle management (create, close, auto-restart), and preview links for forwarded ports.

## Scope
- `backend/codehive/execution/tunnel.py` -- Tunnel lifecycle: create port forward, monitor, close, auto-restart on disconnect
- `backend/codehive/core/tunnel.py` -- Tunnel registry: track active tunnels, generate preview URLs
- `backend/codehive/api/routes/tunnels.py` -- Endpoints: list active tunnels, create tunnel, close tunnel, get preview link
- `web/src/components/TunnelPanel.tsx` -- UI: list active tunnels, preview links, restart/close buttons
- `backend/tests/test_tunnels.py` -- Tunnel management tests

## Dependencies
- Depends on: #40 (SSH connection manager)
- Depends on: #14 (React app for tunnel UI)
