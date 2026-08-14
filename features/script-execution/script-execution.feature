Feature: Resolve and execute repository scripts
  Direct addresses select one local script and preserve raw process behavior.

  @requirement-repository-and-script-boundaries-are-explicit @delta-current-owner-address @delta-added-owner-address
  Scenario: Preserve dotted repository names with the colon boundary
    Given namespace "Pathverse" is enrolled with repository "scripts.tools"
    When the user invokes "Pathverse/scripts.tools:release.publish"
    Then Zush selects base path "release/publish" in that repository

  @requirement-repository-and-script-boundaries-are-explicit @delta-malformed-address
  Scenario: Reject malformed addresses before acquisition
    Given no repository has been materialized
    When the user invokes malformed address "~tools.release"
    Then accepted address forms are reported and acquisition is not attempted

  @requirement-script-selection-is-deterministic @delta-one-inferred-script @delta-exact-executable-file
  Scenario: Select one supported local script
    Given a managed checkout contains only "tasks/cleanup.py" for base path "tasks/cleanup"
    When the user invokes its dot-path address
    Then Zush selects the Python file for execution

  @requirement-script-selection-is-deterministic @delta-multiple-inferred-scripts
  Scenario: Reject ambiguous script suffixes
    Given a checkout contains "tasks/cleanup.py" and "tasks/cleanup.sh"
    When the user invokes dot path "tasks.cleanup"
    Then both candidates are reported and neither is executed

  @requirement-script-selection-is-deterministic @delta-unknown-script
  Scenario: Report an unknown script after materialization
    Given a managed checkout contains no candidate for "tasks.cleanup"
    When the user invokes that dot path
    Then an unknown-script error is reported and nothing executes

  @requirement-supported-scripts-use-native-runners @delta-python-script @delta-required-runner-is-missing
  Scenario: Use the active Python interpreter
    Given a selected Python script prints its interpreter path
    When Zush executes the script
    Then the active Python interpreter is reported

  @requirement-script-arguments-and-results-remain-transparent @delta-raw-arguments @delta-script-failure
  Scenario: Preserve raw arguments and child exit status
    Given a Python script prints its arguments and exits with status 7
    When the user supplies "--arg first -- --flag second"
    Then the script receives those arguments in order and Zush exits with status 7
