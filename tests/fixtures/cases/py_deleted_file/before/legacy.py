def old_login(username, password):
    try:
        return check(username, password)
    except KeyError:
        return False
