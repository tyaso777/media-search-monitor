"""Custom errors for news monitor."""


class NewsMonitorError(Exception):
    """Base error for news monitor failures."""


class PlaywrightUnavailableError(NewsMonitorError):
    """Raised when Playwright fetching is requested but unavailable."""
