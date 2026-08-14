Feature: Layer local aliases over optional remote configuration
  Remote `.zush` configuration remains read-only while local bind and unbind are mutable.

  @requirement-optional-remote-configuration-is-read-only @delta-remote-configuration-exists @delta-remote-configuration-is-absent
  Scenario: Load optional remote configuration without mutating it
    Given the authenticated owner may or may not expose repository ".zush"
    When Zush loads configuration
    Then valid remote aliases are available when present and no repository is written

  @requirement-optional-remote-configuration-is-read-only @delta-invalid-remote-configuration
  Scenario: Report invalid remote configuration
    Given remote map.toml is invalid TOML
    When the user invokes an affected alias
    Then configuration failure is reported before target acquisition

  @requirement-alias-records-have-a-stable-toml-shape @delta-complete-alias
  Scenario: Preserve complete typed alias defaults
    Given remote map.toml defines a target, default arguments, and typed default map
    When Zush loads the alias
    Then every record field retains its declared value and type

  @requirement-local-bindings-overlay-remote-aliases @delta-bind-a-local-alias @delta-override-a-remote-alias
  Scenario: Bind a local alias above a remote alias
    Given remote configuration defines alias "ship"
    When the user binds local alias "ship" to another valid target
    Then the local target is persisted and selected

  @requirement-local-bindings-overlay-remote-aliases @delta-unbind-a-remote-only-alias
  Scenario: Hide a remote alias with a local tombstone
    Given only remote configuration defines alias "ship"
    When the user unbinds alias "ship"
    Then the merged catalog hides it without changing remote map.toml

  @requirement-alias-execution-uses-the-direct-address-pipeline @delta-execute-an-alias @delta-unknown-alias
  Scenario: Execute a known alias and reject an unknown alias
    Given alias "hello" targets "~tools:scripts.hello"
    When the user runs alias "hello" and then alias "missing"
    Then the known alias uses the direct pipeline and the unknown alias acquires nothing

  @requirement-explicit-arguments-follow-alias-defaults @delta-alias-arguments-are-extended
  Scenario: Extend alias default arguments and map
    Given alias "hello" has default argument "base" and a default map
    When the user supplies "--arg extra -- --flag" and an overriding variable
    Then the child receives ordered arguments and the overlaid input object
