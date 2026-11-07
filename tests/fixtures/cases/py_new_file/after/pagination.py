def paginate(items, page, per_page=10):
    start = (page - 1) * per_page
    return items[start : start + per_page]


def page_count(items, per_page=10):
    if per_page <= 0:
        raise ValueError("per_page must be positive")
    return (len(items) + per_page - 1) // per_page
