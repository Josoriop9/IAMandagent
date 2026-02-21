"""
Policy engine for validating operations against defined rules.

This module implements a flexible policy system for controlling
access and enforcing limits on operations.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from hashed.exceptions import HashedError


class PermissionError(HashedError):
    """Raised when a policy rule is violated."""

    pass


@dataclass
class Policy:
    """
    Represents a policy rule for a specific tool or operation.

    Attributes:
        tool_name: Name of the tool or operation
        max_amount: Maximum allowed amount/value (None for unlimited)
        allowed: Whether the operation is allowed at all
        metadata: Additional policy metadata
    """

    tool_name: str
    max_amount: Optional[float] = None
    allowed: bool = True
    metadata: Dict[str, Any] = None

    def __post_init__(self) -> None:
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}

    def validate(self, amount: Optional[float] = None) -> bool:
        """
        Validate if an operation with given amount complies with this policy.

        Args:
            amount: Amount/value to validate

        Returns:
            True if valid, False otherwise
        """
        if not self.allowed:
            return False

        if amount is not None and self.max_amount is not None:
            return amount <= self.max_amount

        return True


class PolicyEngine:
    """
    Policy engine for managing and validating operation policies.

    This class implements the Strategy pattern for flexible policy
    validation and follows the Single Responsibility Principle by
    focusing solely on policy management.

    Example:
        >>> engine = PolicyEngine()
        >>> engine.add_policy("transfer", max_amount=1000.0, allowed=True)
        >>> engine.validate("transfer", amount=500.0)  # Returns True
        >>> engine.validate("transfer", amount=1500.0)  # Raises PermissionError
    """

    def __init__(self) -> None:
        """Initialize the policy engine with an empty policy dictionary."""
        self._policies: Dict[str, Policy] = {}
        self._default_policy = Policy(
            tool_name="default", max_amount=None, allowed=True
        )

    def add_policy(
        self,
        tool_name: str,
        max_amount: Optional[float] = None,
        allowed: bool = True,
        **metadata: Any,
    ) -> None:
        """
        Add or update a policy for a specific tool.

        Args:
            tool_name: Name of the tool or operation
            max_amount: Maximum allowed amount (None for unlimited)
            allowed: Whether the operation is allowed
            **metadata: Additional policy metadata

        Example:
            >>> engine = PolicyEngine()
            >>> engine.add_policy("api_call", max_amount=100, allowed=True)
        """
        self._policies[tool_name] = Policy(
            tool_name=tool_name,
            max_amount=max_amount,
            allowed=allowed,
            metadata=metadata,
        )

    def remove_policy(self, tool_name: str) -> None:
        """
        Remove a policy for a specific tool.

        Args:
            tool_name: Name of the tool

        Raises:
            KeyError: If policy doesn't exist
        """
        del self._policies[tool_name]

    def get_policy(self, tool_name: str) -> Policy:
        """
        Get the policy for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Policy for the tool, or default policy if not found
        """
        return self._policies.get(tool_name, self._default_policy)

    def has_policy(self, tool_name: str) -> bool:
        """
        Check if a policy exists for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            True if policy exists, False otherwise
        """
        return tool_name in self._policies

    def set_default_policy(
        self, max_amount: Optional[float] = None, allowed: bool = True
    ) -> None:
        """
        Set the default policy for tools without specific policies.

        Args:
            max_amount: Maximum allowed amount
            allowed: Whether operations are allowed by default
        """
        self._default_policy = Policy(
            tool_name="default", max_amount=max_amount, allowed=allowed
        )

    def validate(
        self, tool_name: str, amount: Optional[float] = None, **context: Any
    ) -> bool:
        """
        Validate an operation against its policy.

        Args:
            tool_name: Name of the tool or operation
            amount: Amount/value to validate
            **context: Additional context for validation

        Returns:
            True if valid

        Raises:
            PermissionError: If the operation violates the policy

        Example:
            >>> engine = PolicyEngine()
            >>> engine.add_policy("transfer", max_amount=1000.0)
            >>> engine.validate("transfer", amount=500.0)  # OK
            >>> engine.validate("transfer", amount=1500.0)  # Raises PermissionError
        """
        policy = self.get_policy(tool_name)

        if not policy.allowed:
            raise PermissionError(
                f"Operation '{tool_name}' is not allowed",
                details={
                    "tool_name": tool_name,
                    "policy": "denied",
                    "context": context,
                },
            )

        if amount is not None and policy.max_amount is not None:
            if amount > policy.max_amount:
                raise PermissionError(
                    f"Amount {amount} exceeds maximum allowed {policy.max_amount} for '{tool_name}'",
                    details={
                        "tool_name": tool_name,
                        "amount": amount,
                        "max_amount": policy.max_amount,
                        "context": context,
                    },
                )

        return True

    def check_permission(
        self, tool_name: str, amount: Optional[float] = None, **context: Any
    ) -> bool:
        """
        Check if an operation is permitted without raising an exception.

        Args:
            tool_name: Name of the tool or operation
            amount: Amount/value to check
            **context: Additional context

        Returns:
            True if permitted, False otherwise

        Example:
            >>> engine = PolicyEngine()
            >>> engine.add_policy("read", allowed=True)
            >>> engine.check_permission("read")  # True
            >>> engine.add_policy("write", allowed=False)
            >>> engine.check_permission("write")  # False
        """
        try:
            return self.validate(tool_name, amount, **context)
        except PermissionError:
            return False

    def list_policies(self) -> Dict[str, Policy]:
        """
        Get all registered policies.

        Returns:
            Dictionary of tool names to policies
        """
        return self._policies.copy()

    def bulk_add_policies(self, policies: Dict[str, Dict[str, Any]]) -> None:
        """
        Add multiple policies at once.

        Args:
            policies: Dictionary mapping tool names to policy parameters

        Example:
            >>> engine = PolicyEngine()
            >>> engine.bulk_add_policies({
            ...     "transfer": {"max_amount": 1000, "allowed": True},
            ...     "delete": {"allowed": False},
            ... })
        """
        for tool_name, params in policies.items():
            self.add_policy(tool_name, **params)

    def export_policies(self) -> Dict[str, Dict[str, Any]]:
        """
        Export all policies as a dictionary.

        Returns:
            Dictionary representation of all policies

        Example:
            >>> engine = PolicyEngine()
            >>> engine.add_policy("test", max_amount=100)
            >>> policies = engine.export_policies()
        """
        return {
            name: {
                "max_amount": policy.max_amount,
                "allowed": policy.allowed,
                "metadata": policy.metadata,
            }
            for name, policy in self._policies.items()
        }

    def import_policies(self, policies_dict: Dict[str, Dict[str, Any]]) -> None:
        """
        Import policies from a dictionary.

        Args:
            policies_dict: Dictionary of policies to import
        """
        self.bulk_add_policies(policies_dict)
