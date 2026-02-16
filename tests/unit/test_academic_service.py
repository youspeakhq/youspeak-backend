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


def test_normalize_csv_headers_classroom_and_class_id():
    row = {
        "first_name": "Teacher",
        "last_name": "One",
        "email": "t@test.com",
        "classroom_id": "550e8400-e29b-41d4-a716-446655440000",
        "class": "660e8400-e29b-41d4-a716-446655440001",
    }
    result = AcademicService._normalize_csv_headers(row)
    assert result["classroom_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result.get("class_id") == "660e8400-e29b-41d4-a716-446655440001"


def test_normalize_csv_headers_student_number():
    row = {
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "a@test.com",
        "student_id": "2025-001",
    }
    result = AcademicService._normalize_csv_headers(row)
    assert result["student_number"] == "2025-001"


def test_normalize_csv_headers_student_number_aliases():
    for col in ("student_number", "student id", "Student Number"):
        row = {"first_name": "X", "last_name": "Y", "email": "x@y.com", col: "2025-042"}
        result = AcademicService._normalize_csv_headers(row)
        assert result["student_number"] == "2025-042"
