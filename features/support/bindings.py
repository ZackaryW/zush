"""Factory for capability-local thin Behave bindings."""

from __future__ import annotations

from behave import given, then, use_step_matcher, when

from features.support.verification import record_statement, verify_scenario


def bind_capability(capability: str) -> None:
    use_step_matcher("re")

    @given(r".+")
    def given_statement(context) -> None:
        record_statement(context, "given", context.text or "")

    @when(r".+")
    def when_statement(context) -> None:
        record_statement(context, "when", context.text or "")

    @then(r".+")
    def then_statement(context) -> None:
        record_statement(context, "then", context.text or "")
        verify_scenario(context, capability)
