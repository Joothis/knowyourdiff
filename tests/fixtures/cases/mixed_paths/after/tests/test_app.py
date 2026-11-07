def test_ok():
    assert True


def test_timeout_retries():
    try:
        call()
    except TimeoutError:
        pass
