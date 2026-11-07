def handler(request):
    try:
        return {"ok": True, "user": request.user.id}
    except AttributeError:
        return {"ok": False}
