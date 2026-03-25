from tests.playground_helpers import copy_playground, make_subprocess_env, make_test_home, run_zush


def test_provider_service_demo_can_start_and_report(tmp_path) -> None:
    playground = copy_playground(tmp_path, "zush_provider_service_demo")
    home = make_test_home()
    env = make_subprocess_env(home=home)

    first = run_zush(playground, "provider", "info", env=env)
    assert first.returncode == 0
    first_out = first.stdout + first.stderr
    assert "provider-demo" in first_out
    assert "boot=1" in first_out
    assert "status=healthy" in first_out

    restarted = run_zush(playground, "self", "services", "provider-demo", "--restart", env=env)
    assert restarted.returncode == 0

    second = run_zush(playground, "provider", "info", env=env)
    assert second.returncode == 0
    second_out = second.stdout + second.stderr
    assert "provider-demo" in second_out
    assert "boot=2" in second_out
    assert "status=healthy" in second_out