Feature: Discover explicitly trusted GitHub namespaces
  Zush exposes the authenticated owner's repositories and only enrolled foreign namespaces.

  @requirement-authenticated-owner-shorthand @delta-resolve-the-current-owner
  Scenario: Resolve the authenticated owner through tilde
    Given GitHub authenticates the public CLI as owner "alice"
    And owner "alice" exposes repository "tools"
    When the user invokes address "~tools:hello"
    Then repository "alice/tools" is selected

  @requirement-authenticated-owner-shorthand @delta-github-authentication-is-unavailable
  Scenario: Reject current-owner resolution without GitHub authentication
    Given GitHub authentication is unavailable
    When the user invokes address "~tools:hello"
    Then acquisition is not attempted and authentication guidance is reported

  @requirement-explicit-namespace-enrollment-grants-trust @delta-add-an-accessible-namespace @delta-added-namespace-gains-a-repository
  Scenario: Enroll one namespace for present and future repositories
    Given GitHub permits enumeration of owner "Pathverse"
    When the user adds namespace "Pathverse"
    And repository "Pathverse/future-tools" becomes visible
    Then address "Pathverse/future-tools:hello" is trusted without another prompt

  @requirement-explicit-namespace-enrollment-grants-trust @delta-add-an-inaccessible-namespace
  Scenario: Reject an inaccessible namespace
    Given GitHub rejects enumeration of owner "private-org"
    When the user adds namespace "private-org"
    Then the namespace is not persisted or trusted

  @requirement-namespace-enrollment-is-inspectable-and-removable @delta-remove-a-namespace
  Scenario: Remove namespace access without deleting source state
    Given namespace "Pathverse" is enrolled and has a managed checkout
    When the user removes namespace "Pathverse"
    Then new Pathverse addresses are rejected and the checkout remains

  @requirement-repository-exclusions-constrain-discovery @delta-excluded-repository @delta-unmatched-repository
  Scenario: Apply repository exclusions before acquisition
    Given remote configuration excludes "archive-*" for owner "alice"
    When the user invokes "~archive-tools:hello" and "~active-tools:hello"
    Then only repository "alice/active-tools" may reach Saucepan
