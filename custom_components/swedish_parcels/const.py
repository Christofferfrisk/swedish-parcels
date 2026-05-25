from __future__ import annotations

DOMAIN = "swedish_parcels"

CONF_IMAP_HOST = "imap_host"
CONF_IMAP_PORT = "imap_port"
CONF_IMAP_USER = "imap_user"
CONF_IMAP_PASSWORD = "imap_password"
CONF_IMAP_MAILBOX = "imap_mailbox"
CONF_PARCEL_SENDERS = "parcel_senders"
CONF_AIRMEE_PHONE_HASH = "airmee_phone_hash"
CONF_SCAN_INTERVAL_MIN = "scan_interval_min"

DEFAULT_PORT = 993
DEFAULT_MAILBOX = "INBOX"
DEFAULT_SCAN_INTERVAL_MIN = 15
DEFAULT_SENDERS = (
    "bring.com,airmee.com,amazon.se,zalando.se,postnord.com,"
    "budbee.com,instabox,dhl.com,schenker.com"
)
