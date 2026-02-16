"""Unit tests for AcademicService (pure logic, no DB)."""

import pytest

from app.services.academic_service import AcademicService


def test_normalize_csv_headers_standard():
    row = {"first_name": "Alice", "last_name": "Smith", "email": "a@b.com"}
    result = AcademicService._normalize_csv_headers(row)
    assert result["first_name"] == "Alice"
    assert result["last_name"] == "Smith"
    assert result["email"] == "a@b.com"


def test_normalize_csv_headers_flexible():
    row = {"First Name": "Bob", "Last Name": "Jones", "E-mail": "b@c.com"}
    result = AcademicService._normalize_csv_headers(row)
    assert result["first_name"] == "Bob"
    assert result["last_name"] == "Jones"
    assert result["email"] == "b@c.com"


def test_normalize_csv_headers_alternatives():
    row = {"firstname": "X", "surname": "Y", "mail": "x@y.com"}
    result = AcademicService._normalize_csv_headers(row)
    assert result["first_name"] == "X"
    assert result["last_name"] == "Y"
    assert result["email"] == "x@y.com"


def test_normalize_csv_headers_empty():
    row = {}
    result = AcademicService._normalize_csv_headers(row)
    assert result == {}


def test_normalize_csv_headers_strips_whitespace():
    row = {"first_name": "  Alice  ", "last_name": "Smith", "email": ""}
    result = AcademicService._normalize_csv_headers(row)
    assert result["first_name"] == "Alice"
    assert result["email"] == ""
