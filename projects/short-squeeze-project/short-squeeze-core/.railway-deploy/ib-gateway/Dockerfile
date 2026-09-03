# Interactive Brokers Gateway for Railway private networking.
# The screener connects via IBKR_HOST=<this-service>.railway.internal and IBKR_PORT=4004 (paper).
FROM ghcr.io/gnzsnz/ib-gateway:stable

# Configure on the Railway service (never commit credentials):
#   TWS_USERID          — IBKR username
#   TWS_PASSWORD        — IBKR password
#   TRADING_MODE        — paper (default) or live
#   TWS_ACCEPT_INCOMING — accept
#   READ_ONLY_API       — yes
