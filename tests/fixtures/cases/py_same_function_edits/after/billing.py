def invoice(order, customer):
    subtotal = order.subtotal - customer.credit
    lines = []
    for item in order.items:
        lines.append(item.name)
    notes = "thanks"
    footer = "bye"
    header = "hello"
    if subtotal < 0:
        raise ValueError("credit exceeds subtotal")
    return {"subtotal": subtotal, "lines": lines, "notes": notes}


def unrelated():
    return 1
