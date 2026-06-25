from firebase_admin import auth


def verify_token(token):

    return auth.verify_id_token(token)


def get_user(uid):

    return auth.get_user(uid)