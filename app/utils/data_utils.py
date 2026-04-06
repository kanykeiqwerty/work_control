from datetime import date, datetime, timedelta


def get_target_date():

    today = datetime.today().date()

    weekday = today.weekday()

    target_date = today - timedelta(days=1)

    return target_date


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


# target=get_target_date()
# print(format_report_date(target))
# print(format_sheet_date(target))