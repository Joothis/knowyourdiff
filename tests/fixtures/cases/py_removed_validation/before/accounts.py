def delete_account(user, account):
    if not user.is_admin:
        raise PermissionError("admins only")
    account.delete()
    return True
