#!/usr/bin/env python3
"""App Store Connect plumbing for Sweep, through the API (key ZRL2ZT22XY).

  python3 tools/asc_setup.py profile   register the bundle id if needed, mint (or reuse) the
                                       App Store profile, install it, write profile_uuid.txt
  python3 tools/asc_setup.py app       print the App Store Connect app id (the record itself
                                       has to be made in the web UI; the API can't create it)

Signing is manual: a command-line build has no Apple ID signed into Xcode for automatic signing.
"""
import base64, pathlib, sys
sys.path.insert(0, "/Users/joshgreenman/Experiments/singing-stairs/tools")
from asc import call  # import call() directly; the asc.py CLI truncates long responses

BUNDLE_ID = "com.joshgreenman.sweep"
NAME = "Sweep"
HERE = pathlib.Path(__file__).resolve().parent.parent


def bundle_record():
    s, b = call("GET", f"/v1/bundleIds?filter[identifier]={BUNDLE_ID}&limit=5")
    for r in b.get("data", []):
        if r["attributes"]["identifier"] == BUNDLE_ID:
            return r["id"]
    s, b = call("POST", "/v1/bundleIds", {"data": {"type": "bundleIds", "attributes": {
        "identifier": BUNDLE_ID, "name": NAME, "platform": "IOS"}}})
    if s != 201:
        sys.exit(f"bundle id create failed: {s} {b}")
    print("registered bundle id", BUNDLE_ID)
    return b["data"]["id"]


DIST_CERT = "Q2742CLDGU"  # the Apple Distribution identity in this Mac's keychain (serial 3DC8E59E...)


def dist_cert():
    return DIST_CERT
    s, b = call("GET", "/v1/certificates?limit=50")
    for c in b.get("data", []):
        a = c["attributes"]
        if a["certificateType"] in ("DISTRIBUTION", "IOS_DISTRIBUTION") and "Josh Greenman" in a.get("name", "") + a.get("displayName", ""):
            return c["id"]
    sys.exit("no distribution certificate found")


def profile():
    bid = bundle_record()
    s, b = call("GET", f"/v1/bundleIds/{bid}/profiles?limit=50")
    prof = next((p for p in b.get("data", []) if p["attributes"]["profileType"] == "IOS_APP_STORE"
                 and p["attributes"]["profileState"] == "ACTIVE"), None)
    if prof is None:
        s, b = call("POST", "/v1/profiles", {"data": {"type": "profiles",
            "attributes": {"name": f"{NAME} App Store", "profileType": "IOS_APP_STORE"},
            "relationships": {"bundleId": {"data": {"type": "bundleIds", "id": bid}},
                              "certificates": {"data": [{"type": "certificates", "id": dist_cert()}]}}}})
        if s != 201:
            sys.exit(f"profile create failed: {s} {b}")
        prof = b["data"]
        print("minted profile")
    a = prof["attributes"]
    dest = pathlib.Path.home() / "Library/MobileDevice/Provisioning Profiles" / f"{a['uuid']}.mobileprovision"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(base64.b64decode(a["profileContent"]))
    (HERE / "profile_uuid.txt").write_text(a["uuid"] + "\n")
    print("profile", a["name"], a["uuid"], "expires", a["expirationDate"])


def app():
    s, b = call("GET", f"/v1/apps?filter[bundleId]={BUNDLE_ID}")
    if not b.get("data"):
        sys.exit("no App Store Connect app record yet; create it in the web UI")
    print(b["data"][0]["id"], b["data"][0]["attributes"]["name"])


if __name__ == "__main__":
    {"profile": profile, "app": app}[sys.argv[1] if len(sys.argv) > 1 else "profile"]()
