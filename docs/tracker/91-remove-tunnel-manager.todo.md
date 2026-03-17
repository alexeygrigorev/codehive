# Issue #91: Remove tunnel manager from backend

## Problem

The backend has a tunnel manager (SSH tunnel creation, active tunnels tracking) that was built from the original brainstorm. This is not needed — the deployment model is:

1. Codehive runs on a remote server (e.g., a VPS)
2. The client (mobile app, web browser, CLI) creates an SSH tunnel to the server: `ssh -L 7433:localhost:7433 myserver`
3. The client connects to `localhost:7433` through the tunnel

The tunnel is a client-side concern, not a backend concern. The backend should not manage tunnels.

## Requirements

- [ ] Remove tunnel manager code from backend (execution/tunnel.py or similar)
- [ ] Remove tunnel-related API routes if any
- [ ] Remove tunnel-related UI elements (web "Active Tunnels" section, mobile tunnels screen)
- [ ] Remove tunnel-related database models/tables if any
- [ ] Clean up any references in config, tests, imports
