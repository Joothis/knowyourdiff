def invoice(order, customer):
    subtotal = order.subtotal
    lines = []
    for item in order.items:
        lines.append(item.name)
    notes = "thanks"
    footer = "bye"
    header = "hello"
    return {"subtotal": subtotal, "lines": lines, "notes": notes}


def unrelated():
    return 1
