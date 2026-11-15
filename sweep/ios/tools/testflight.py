#!/usr/bin/env python3
"""TestFlight for Sweep, internal testing only.

  python3 tools/testflight.py          make sure the internal group "Me" exists with Josh in it
                                       (it gets every build automatically), then show build status
  python3 tools/testflight.py --wait   same, and wait for the newest build to finish processing

Internal groups need no Beta App Review. Never submit Sweep to the public App Store without asking Josh.
"""
import sys, time
sys.path.insert(0, "/Users/joshgreenman/Experiments/singing-stairs/tools")
from asc import call

APP = "6834559962"            # App Store Connect id for "Sweep: NYC Street Cleaning"
GROUP = "Me"
GLOVEBOX = "6834539192"       # Seltos Glovebox; its internal group "Me" already holds Josh's tester record


def josh_email():
    # Read Josh's address from the Glovebox group instead of writing it into this (public) repo.
    b = need(call("GET", f"/v1/apps/{GLOVEBOX}/betaGroups?limit=50"), "listing Glovebox groups")
    g = next(g for g in b["data"] if g["attributes"]["name"] == GROUP)
    t = need(call("GET", f"/v1/betaGroups/{g['id']}/betaTesters"), "listing Glovebox testers")
    return t["data"][0]["attributes"]["email"]


def need(r, what):
    s, b = r
    if s not in (200, 201, 204):
        sys.exit(f"{what} failed: {s} {str(b)[:300]}")
    return b


def group():
    b = need(call("GET", f"/v1/apps/{APP}/betaGroups?limit=50"), "listing groups")
    g = next((g for g in b["data"] if g["attributes"]["name"] == GROUP), None)
    if g is None:
        g = need(call("POST", "/v1/betaGroups", {"data": {"type": "betaGroups",
            "attributes": {"name": GROUP, "isInternalGroup": True, "hasAccessToAllBuilds": True},
            "relationships": {"app": {"data": {"type": "apps", "id": APP}}}}}), "creating group")["data"]
        print(f"created internal group {GROUP!r}")
    gid = g["id"]
    t = need(call("GET", f"/v1/betaGroups/{gid}/betaTesters"), "listing testers")
    EMAIL = josh_email()
    if not any(x["attributes"].get("email") == EMAIL for x in t["data"]):
        # Adding an existing tester record by id returns 409 here; posting the email works.
        need(call("POST", "/v1/betaTesters", {"data": {"type": "betaTesters",
            "attributes": {"email": EMAIL, "firstName": "Josh", "lastName": "Greenman"},
            "relationships": {"betaGroups": {"data": [{"type": "betaGroups", "id": gid}]}}}}), "adding tester")
        print("added Josh to the group")
    t = need(call("GET", f"/v1/betaGroups/{gid}/betaTesters"), "listing testers")
    print("group", GROUP, "testers:", [x["attributes"].get("email") for x in t["data"]])
    return gid


def builds():
    b = need(call("GET", f"/v1/builds?filter[app]={APP}&limit=5&sort=-uploadedDate"
                         "&fields[builds]=version,processingState,uploadedDate,expired"), "listing builds")
    return b["data"]


if __name__ == "__main__":
    gid = group()
    deadline = time.time() + 1500
    while True:
        bs = builds()
        for x in bs:
            a = x["attributes"]
            print("build", a["version"], a["processingState"], a["uploadedDate"])
        if "--wait" not in sys.argv or (bs and bs[0]["attributes"]["processingState"] in ("VALID", "FAILED", "INVALID")) or time.time() > deadline:
            break
        time.sleep(30)
    if bs and bs[0]["attributes"]["processingState"] == "VALID":
        bid = bs[0]["id"]
        s, d = call("GET", f"/v1/builds/{bid}/buildBetaDetail")
        if s == 200:
            print("internal state:", d["data"]["attributes"].get("internalBuildState"))
