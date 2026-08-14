Feature: Support the declared Python runtime floor
  Zush packages install and run at the supported boundary while excluding older runtimes.

  @requirement-python-3-11-is-the-minimum-supported-runtime @delta-install-and-run-on-python-3-11
  Scenario: Run the built CLI on Python 3.11
    Given a wheel built from the Zush project
    When it is installed into an isolated Python 3.11 environment
    Then the public CLI reports the packaged Zush version

  @requirement-python-3-11-is-the-minimum-supported-runtime @delta-reject-an-older-python-runtime
  Scenario: Exclude Python 3.10 in distribution metadata
    Given a wheel built from the Zush project
    When an installer evaluates it for Python 3.10
    Then the package is rejected as requiring Python 3.11 or newer
