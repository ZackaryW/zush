Feature: Materialize repository sources through Saucepan
  Zush generates acquisition-only index records and delegates working-copy lifecycle.

  @requirement-namespace-inventory-supplies-acquisition-metadata @delta-manifest-less-repository-is-inventoried @delta-generated-index-remains-local
  Scenario: Generate local pinned metadata for a manifest-less repository
    Given GitHub reports repository "alice/tools" at commit "abc123"
    When Zush refreshes the namespace inventory
    Then the private local Saucepan index pins "alice/tools" to "abc123" without command metadata
    And no remote configuration repository is changed

  @requirement-saucepan-owns-repository-lifecycle @delta-first-invocation-materializes-a-repository
  Scenario: Materialize an absent repository on first invocation
    Given visible repository "alice/tools" is not installed
    When the user invokes "~tools:hello"
    Then Saucepan installs "alice/tools" and Zush resolves from its reported path

  @requirement-saucepan-owns-repository-lifecycle @delta-existing-installation-is-reused
  Scenario: Reuse an existing managed checkout without update
    Given Saucepan already manages repository "alice/tools"
    When the user invokes "~tools:hello"
    Then Zush uses its reported path without install or update

  @requirement-installed-identity-follows-provenance @delta-repository-manifest-chooses-another-name
  Scenario: Locate a repository whose manifest selects another identity
    Given Saucepan records "alice/tools" as identity "tools-cli"
    When the user invokes "~tools:hello"
    Then Zush locates identity "tools-cli" through repository provenance

  @requirement-updates-are-explicit @delta-execute-an-installed-repository @delta-explicit-update
  Scenario: Update only through the explicit command
    Given Saucepan manages two visible repositories
    When the user executes one script and later runs "zush update"
    Then execution performs no update and the update command refreshes both repositories

  @requirement-materialization-failures-preserve-safety @delta-saucepan-installation-fails
  Scenario: Do not execute from a failed acquisition
    Given Saucepan fails to install visible repository "alice/tools"
    When the user invokes "~tools:hello"
    Then the failure is reported and no script is executed
