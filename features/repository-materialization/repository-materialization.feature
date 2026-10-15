Feature: Materialize exact repository commits through Saucepan
  Zush selects retained outputs through the current SDK.

  Scenario: Materialize an absent repository on first invocation
    Given a visible repository has an exact Git commit
    When the user invokes its script
    Then Zush delegates materialization and executes the retained output

  Scenario: Explicit updates preserve ordinary execution behavior
    Given an installed repository remains visible
    When execution and an explicit update are requested
    Then only update refreshes the installed repository selection

  Scenario: Failed acquisition does not execute a script
    Given repository materialization fails
    When the user invokes its script
    Then Zush reports the failure without executing it
