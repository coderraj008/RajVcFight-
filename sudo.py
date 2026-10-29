import json, os

SUDO_FILE = "sudoers.json"

if not os.path.exists(SUDO_FILE):
    with open(SUDO_FILE, "w") as f:
        json.dump([], f)

def load_sudoers():
    with open(SUDO_FILE, "r") as f:
        return json.load(f)

def save_sudoers(data):
    with open(SUDO_FILE, "w") as f:
        json.dump(data, f)

async def get_sudoers():
    return load_sudoers()

async def add_sudoer(uid):
    data = load_sudoers()
    if uid not in data:
        data.append(uid)
        save_sudoers(data)

async def del_sudoer(uid):
    data = load_sudoers()
    if uid in data:
        data.remove(uid)
        save_sudoers(data)
