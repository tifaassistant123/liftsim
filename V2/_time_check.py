import datetime
tz = datetime.timezone(datetime.timedelta(hours=8))
now = datetime.datetime.now(tz)
print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print(f"Day of week: {now.strftime('%A')}")
