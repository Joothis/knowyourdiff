def greet(name):
    """Return a greeting for ``name``."""
    message = "Hello, " + name
    message = message.strip()
    message = message + "!"
    return message


def farewell(name):
    return "Bye, " + name
