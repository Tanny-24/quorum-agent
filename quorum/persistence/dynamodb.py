"""Small DynamoDB adapter exposing the conditional semantics QUORUM needs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError


class DynamoDBStore:
    """Use a single-table client; callers supply a boto3 Table-like object."""

    def __init__(self, table: Any) -> None:
        self.table = table

    @staticmethod
    def _conditional_failed(exc: ClientError) -> bool:
        return exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"

    def put_idempotent(self, item: dict[str, Any]) -> bool:
        try:
            self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(pk)")
            return True
        except ClientError as exc:
            if self._conditional_failed(exc):
                return False
            raise

    def transition(self, pk: str, expected: str, target: str) -> bool:
        try:
            self.table.update_item(
                Key={"pk": pk},
                UpdateExpression="SET #status = :target, updated_at = :now",
                ConditionExpression="#status = :expected",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":expected": expected,
                    ":target": target,
                    ":now": datetime.now(timezone.utc).isoformat(),
                },
            )
            return True
        except ClientError as exc:
            if self._conditional_failed(exc):
                return False
            raise

    def confirm_assignment(self, shift_role_pk: str, assignment: dict[str, Any], capacity: int) -> bool:
        """Atomically increment the role seat count only while capacity remains."""
        try:
            self.table.update_item(
                Key={"pk": shift_role_pk},
                UpdateExpression="SET filled = if_not_exists(filled, :zero) + :one, last_assignment = :assignment",
                ConditionExpression="attribute_not_exists(filled) OR filled < :capacity",
                ExpressionAttributeValues={
                    ":zero": 0,
                    ":one": 1,
                    ":capacity": capacity,
                    ":assignment": assignment,
                },
            )
            return True
        except ClientError as exc:
            if self._conditional_failed(exc):
                return False
            raise

    def spend_attention(self, budget_pk: str, allowance: int) -> bool:
        try:
            self.table.update_item(
                Key={"pk": budget_pk},
                UpdateExpression="SET spent = if_not_exists(spent, :zero) + :one",
                ConditionExpression="attribute_not_exists(spent) OR spent < :allowance",
                ExpressionAttributeValues={":zero": 0, ":one": 1, ":allowance": allowance},
            )
            return True
        except ClientError as exc:
            if self._conditional_failed(exc):
                return False
            raise
