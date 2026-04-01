"""Exceptions for the pybirno library."""


class BirError(Exception):
    """Base exception for BIR API errors."""


class BirConnectionError(BirError):
    """Raised when unable to connect to the BIR API."""


class BirAuthenticationError(BirError):
    """Raised when authentication with the BIR API fails."""


class BirResponseError(BirError):
    """Raised when the BIR API returns an unexpected response."""
