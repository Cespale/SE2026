import pytest
from pydantic import ValidationError

from app.schemas import AuditIn


def test_audit_status_allows_final_decisions_only():
    approved = AuditIn(auditStatus=1)
    rejected = AuditIn(auditStatus=2)

    assert approved.auditStatus == 1
    assert rejected.auditStatus == 2
    assert approved.rejectReason is None
    assert rejected.rejectReason is None
    assert approved.model_dump() == {"auditStatus": 1, "rejectReason": None}
    assert rejected.model_dump() == {"auditStatus": 2, "rejectReason": None}
    assert isinstance(approved.auditStatus, int)

    for invalid_status in (0, 3, -1):
        with pytest.raises(ValidationError) as error:
            AuditIn(auditStatus=invalid_status)

        assert error.value.errors()[0]["type"] == "literal_error"
        assert error.value.error_count() == 1
        assert error.value.errors()[0]["loc"] == ("auditStatus",)
        assert error.value.errors()[0]["input"] == invalid_status
