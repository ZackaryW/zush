from features.support.verification import verify_scenario


def verify(context) -> None:
    verify_scenario(context, "command-aliases")
