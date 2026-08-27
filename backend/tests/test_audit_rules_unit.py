import pytest
from pydantic import ValidationError

from app.schemas import AuditIn


def test_audit_status_allows_final_decisions_only():
    assert AuditIn(auditStatus=1).auditStatus == 1
    assert AuditIn(auditStatus=2).auditStatus == 2

    for invalid_status in (0, 3, -1):
        with pytest.raises(ValidationError) as error:
            AuditIn(auditStatus=invalid_status)

        assert error.value.errors()[0]["type"] == "literal_error"
