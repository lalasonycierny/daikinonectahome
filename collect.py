import os, csv, datetime as dt, json, requests

IDP = "https://idp.onecta.daikineurope.com/v1/oidc/token"
API = "https://api.onecta.daikineurope.com/v1/gateway-devices"
OUT = "datadir/history.csv"

def get_access_token():
    r = requests.post(IDP, data={
        "grant_type": "refresh_token",
        "refresh_token": os.environ["DAIKIN_REFRESH_TOKEN"],
        "client_id": os.environ["DAIKIN_CLIENT_ID"],
        "client_secret": os.environ["DAIKIN_CLIENT_SECRET"],
    }, timeout=30)
    r.raise_for_status()
    j = r.json()
    new = j.get("refresh_token")
    if new and new != os.environ["DAIKIN_REFRESH_TOKEN"]:
        open("new_refresh_token.txt", "w").write(new)
    return j["access_token"]

def val(d, *path):
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d

def main():
    token = get_access_token()
    r = requests.get(API, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code == 429:
        print("Rate limited, retry-after:", r.headers.get("Retry-After"))
        return
    r.raise_for_status()
    devices = r.json()
    if os.environ.get("DEBUG"):
        print(json.dumps(devices, indent=1)[:6000])

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for d in devices:
        for mp in d.get("managementPoints", []):
            if mp.get("embeddedId") != "climateControl":
                continue
            name = val(mp, "name", "value") or d["id"][:8]
            mode = val(mp, "operationMode", "value")
            rows.append([
                now, d["id"], name,
                val(mp, "sensoryData", "value", "roomTemperature", "value"),
                val(mp, "sensoryData", "value", "outdoorTemperature", "value"),
                val(mp, "temperatureControl", "value", "operationModes", mode,
                    "setpoints", "roomTemperature", "value") if mode else None,
                mode,
                val(mp, "onOffMode", "value"),
            ])

    new_file = not os.path.exists(OUT)
    with open(OUT, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["time", "device_id", "name", "room_temp",
                        "outdoor_temp", "setpoint", "mode", "power"])
        w.writerows(rows)
    print(f"Saved {len(rows)} rows")

main()
