"""Persistence model base; SQL migration remains authoritative."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
