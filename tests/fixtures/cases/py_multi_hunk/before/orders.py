def total(order):
    return sum(item.price for item in order.items)


def tax(amount):
    return amount * 0.18


def shipping(order):
    return 50


def describe(order):
    return f"{len(order.items)} items"


def discount(order):
    return 0
