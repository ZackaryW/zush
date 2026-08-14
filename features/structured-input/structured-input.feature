Feature: Deliver optional typed input without consuming stdin
  Invocation maps preserve JSON types and are cleaned up after execution.

  @requirement-invocation-values-form-one-object @delta-invocation-value-overrides-alias-default @delta-map-replacement-is-shallow
  Scenario: Overlay invocation values above alias defaults
    Given an alias default map contains nested and scalar values
    When maps and assignments replace those top-level keys
    Then the child reads the shallowly overlaid typed object

  @requirement-string-and-casted-assignments-are-validated @delta-float-assignment @delta-boolean-assignment
  Scenario: Preserve casted JSON scalar types
    Given a script reads its Zush input file
    When the invocation casts a float and a false boolean
    Then the child reads a JSON number and JSON boolean

  @requirement-string-and-casted-assignments-are-validated @delta-invalid-cast @requirement-map-input-must-be-a-json-object @delta-non-object-map
  Scenario: Reject invalid structured input before execution
    Given a script would record if it started
    When the invocation supplies an invalid cast or non-object map
    Then Zush reports the invalid input and the script never starts

  @requirement-typed-input-travels-through-a-temporary-json-file @delta-script-reads-structured-input @delta-temporary-input-cleanup
  Scenario: Expose and clean up the temporary JSON file
    Given a script records its input path and inherited stdin
    When it exits after reading structured input
    Then the file contained the complete typed object and no longer exists
