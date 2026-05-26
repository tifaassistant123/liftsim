import json

with open('C:/Users/tifaa/.openclaw/cron/jobs.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
jobs = data if isinstance(data, list) else data.get('jobs', [])

# Check the lunch reminders
for j in jobs:
    name = j.get('name', '')
    # Show all non-spawn-queue jobs
    if 'queue' not in name.lower():
        print(f'Name: {name}')
        print(f'  enabled: {j.get("enabled")}')
        print(f'  schedule: {j.get("schedule", {})}')
        print(f'  agentId: {j.get("agentId")}')
        print(f'  sessionTarget: {j.get("sessionTarget")}')
        print(f'  sessionKey: {j.get("sessionKey")}')
        print(f'  payload kind: {j.get("payload", {}).get("kind")}')
        print(f'  delivery: {j.get("delivery", {})}')
        print()
