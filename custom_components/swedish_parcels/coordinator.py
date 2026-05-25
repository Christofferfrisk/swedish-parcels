from __future__ import annotations

import hashlib
import imaplib
import logging
from datetime import date, datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .parsers import REGISTRY
from .store import Parcel, ShipmentStore
from .trackers.airmee import AirmeeTracker

from .const import (
    CONF_AIRMEE_PHONE_HASH,
    CONF_IMAP_HOST,
    CONF_IMAP_MAILBOX,
    CONF_IMAP_PASSWORD,
    CONF_IMAP_PORT,
    CONF_IMAP_USER,
    CONF_LOOKBACK_DAYS,
    CONF_PARCEL_SENDERS,
    CONF_RETENTION_DAYS,
    CONF_SCAN_INTERVAL_MIN,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MAILBOX,
    DEFAULT_PORT,
    DEFAULT_RETENTION_DAYS,
    DEFAULT_SCAN_INTERVAL_MIN,
)

_LOGGER = logging.getLogger(__name__)


class SwedishParcelsCoordinator(DataUpdateCoordinator[dict[str, Parcel]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        opts = {**entry.data, **entry.options}
        interval = int(opts.get(CONF_SCAN_INTERVAL_MIN, DEFAULT_SCAN_INTERVAL_MIN))
        super().__init__(
            hass,
            _LOGGER,
            name="swedish_parcels",
            update_interval=timedelta(minutes=interval),
        )
        self._store = ShipmentStore()
        self._seen_message_ids: set[str] = set()

    async def _async_update_data(self) -> dict[str, Parcel]:
        try:
            await self.hass.async_add_executor_job(self._fetch_and_parse_sync)
            await self.hass.async_add_executor_job(self._refresh_live_sync)
        except Exception as e:
            raise UpdateFailed(str(e)) from e

        opts = {**self.entry.data, **self.entry.options}
        retention = int(opts.get(CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS))
        dropped = self._store.prune_delivered_older_than(
            datetime.now(timezone.utc), timedelta(days=retention)
        )
        if dropped:
            _LOGGER.debug("Pruned %d delivered parcel(s) older than %d days", dropped, retention)

        # Only surface parcels with something meaningful to show — skips
        # marketing/feedback noise that would otherwise become 'unknown'
        # state entities.
        return {p.key: p for p in self._store.all() if _has_signal(p)}


def _has_signal(p: Parcel) -> bool:
    if p.tracking_number or p.status:
        return True
    if p.records and p.records[0].order_ref:
        return True
    return False

    def _fetch_and_parse_sync(self) -> None:
        opts = {**self.entry.data, **self.entry.options}
        senders = [s.strip() for s in opts[CONF_PARCEL_SENDERS].split(",") if s.strip()]
        lookback = int(opts.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS))
        since = (date.today() - timedelta(days=lookback)).strftime("%d-%b-%Y")
        conn = imaplib.IMAP4_SSL(opts[CONF_IMAP_HOST], int(opts.get(CONF_IMAP_PORT, DEFAULT_PORT)))
        conn.login(opts[CONF_IMAP_USER], opts[CONF_IMAP_PASSWORD])
        conn.select(opts.get(CONF_IMAP_MAILBOX, DEFAULT_MAILBOX), readonly=True)
        try:
            for sender in senders:
                criteria = f'(SINCE {since} FROM "{sender}")'
                typ, data = conn.uid("SEARCH", None, criteria)
                if typ != "OK" or not data or not data[0]:
                    continue
                for uid in data[0].split():
                    typ, msg_data = conn.uid("FETCH", uid, "(RFC822)")
                    if typ != "OK" or not msg_data or not msg_data[0]:
                        continue
                    raw = msg_data[0][1]
                    if not isinstance(raw, (bytes, bytearray)):
                        continue
                    digest = hashlib.sha1(bytes(raw)).hexdigest()
                    if digest in self._seen_message_ids:
                        continue
                    self._seen_message_ids.add(digest)
                    msg = BytesParser(policy=policy.default).parsebytes(bytes(raw))
                    for parser in REGISTRY:
                        if parser.matches(msg):
                            self._store.add(parser.parse(msg))
                            break
        finally:
            conn.logout()

    def _refresh_live_sync(self) -> None:
        opts = {**self.entry.data, **self.entry.options}
        phone_hash = opts.get(CONF_AIRMEE_PHONE_HASH)
        if not phone_hash:
            return
        tracker = AirmeeTracker(phone_number_hash=phone_hash)
        for parcel in list(self._store.open_parcels()):
            if parcel.carrier != "airmee" or not parcel.tracking_number:
                continue
            try:
                live = tracker.fetch(parcel.tracking_number)
            except Exception as e:
                _LOGGER.debug("Airmee live fetch failed for %s: %s", parcel.tracking_number, e)
                continue
            if live is not None:
                self._store.attach_live(parcel, live)
