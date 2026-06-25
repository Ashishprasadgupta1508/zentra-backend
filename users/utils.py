from django.http import JsonResponse

def success(data):

    return JsonResponse({

        "success":True,

        "data":data

    })


def error(msg):

    return JsonResponse({

        "success":False,

        "message":msg

    })