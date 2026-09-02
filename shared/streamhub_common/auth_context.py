from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuthContext:
    user_id: UUID
    user_type: int
    status: int

    @property
    def is_creator(self) -> bool:
        return self.user_type >= 1 and self.status == 0

    @property
    def is_admin(self) -> bool:
        return self.user_type >= 2 and self.status == 0
