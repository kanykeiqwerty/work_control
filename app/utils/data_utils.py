# from datetime import date, timedelta
# # import logging

# # logging.basicConfig(
# #     level=logging.INFO,
# #     format="%(asctime)s [%(levelname)s] %(message)s",
# #     datefmt="%Y-%m-%d %H:%M:%S",
# # )
# # logger = logging.getLogger(__name__)
 

# def get_target_data(today: date | None=None)->date | None:
#     if today is None:
#         today=date.today()

#     weekday=today.weekday()

#     if weekday in (5, 6):
#         # logger.info("")
#         return None
    

#     if weekday == 0:
#         check_date=today-timedelta(days=3)
#         # logger.info("")

#     else:
#         check_date=today-timedelta(days=1)

#         # logger.info("")

#     return check_date



# def format_date(d:date)->str:
#     return d.strftime("%d.%m.%Y")


# def weekday_name(weekday:int)->str:
#     names = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
#     return names[weekday]


# def main():
    
    
#     check_date = get_target_data()
#     print(format_date(check_date), (weekday_name(check_date.weekday())))
#     if check_date is None:
#         # logger.info("Проверка не требуется. Завершение.")
#         return
 
#     # logger.info(f"Дата для проверки: {format_date(check_date)} ({weekday_name(check_date.weekday())})")
    
 
 
# if __name__ == "__main__":
#     main()



# target=get_target_data()
# print(target)


from datetime import datetime, timedelta


def get_target_date():

    today = datetime.today().date()

    weekday = today.weekday()

    if weekday == 0:
        target_date = today - timedelta(days=3)
    else:
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


target=get_target_date()
print(format_report_date(target))