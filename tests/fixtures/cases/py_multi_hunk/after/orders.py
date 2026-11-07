def total(order):
    return sum(item.price * item.quantity for item in order.items)


def tax(amount):
    return amount * 0.18


def shipping(order):
    return 50


def describe(order):
    return f"{len(order.items)} items"


def discount(order):
    if order.coupon and order.coupon.expires_at >= order.created_at:
        return order.coupon.amount
    return 0
