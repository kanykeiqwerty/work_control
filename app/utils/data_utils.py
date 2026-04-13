# from datetime import date, datetime, timedelta


# def get_target_date():

#     today = datetime.today().date()

#     weekday = today.weekday()

#     target_date = today - timedelta(days=1)

#     return target_date


# def format_sheet_date(date):

#     return date.strftime("%d.%m.%Y")


# def format_report_date(date):

#     weekday_names = [
#         "понедельник",
#         "вторник",
#         "среда",
#         "четверг",
#         "пятница",
#         "суббота",
#         "воскресенье"
#     ]

#     weekday = weekday_names[date.weekday()]

#     return f"{date.strftime('%d.%m.%Y')} ({weekday})"


# # target=get_target_date()
# # print(format_report_date(target))
# # print(format_sheet_date(target))

from datetime import datetime, date, timedelta


def get_target_date():
    today = datetime.today().date()
    
    weekday = today.weekday()

    if weekday == 0:  # понедельник
        # пятница, суббота, воскресенье
        return [
            today - timedelta(days=3),
            today - timedelta(days=2),
            today - timedelta(days=1),
        ]
    else:
        # обычный день — только вчера
        return [today - timedelta(days=1)]


def format_sheet_date(date):
    return date.strftime("%d.%m.%Y")


def format_report_date(date):
    weekday_names = [
        "понедельник",
        "вторник",
        "среда",
        "четверг",
        "пятница",
        "суббота",
        "воскресенье"
    ]

    weekday = weekday_names[date.weekday()]
    return f"{date.strftime('%d.%m.%Y')} ({weekday})"


# пример использования
# targets = get_target_date()

# for d in targets:
#     print(format_report_date(d))
#     print(format_sheet_date(d))