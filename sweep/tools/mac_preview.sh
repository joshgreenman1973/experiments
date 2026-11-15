#!/bin/sh
# Build a Mac Catalyst copy of the app (in a scratch folder, project untouched) and launch it,
# so the screens can be checked on this Mac. Args are passed to the app, e.g.
#   tools/mac_preview.sh -sweepPick 40.674783,-73.976351
#   tools/mac_preview.sh -sweepDemoParked 40.674783,-73.976351
#   tools/mac_preview.sh -sweepMap -sweepMapTap 40.674783,-73.976351   (map of cleaning days, block selected)
set -e
W=${SWEEP_PREVIEW_DIR:-$TMPDIR/sweep-catalyst}
mkdir -p "$W/proj"
pkill -f "Debug-maccatalyst/Sweep.app/Contents/MacOS/Sweep" || true
rsync -a --delete --exclude build "$(dirname "$0")/../ios/" "$W/proj/"
sed -i '' 's/TARGETED_DEVICE_FAMILY = 1;/TARGETED_DEVICE_FAMILY = "1,2"; SUPPORTS_MACCATALYST = YES; DERIVE_MACCATALYST_PRODUCT_BUNDLE_IDENTIFIER = NO;/' "$W/proj/Sweep.xcodeproj/project.pbxproj"
xcodebuild -project "$W/proj/Sweep.xcodeproj" -scheme Sweep -configuration Debug -destination 'platform=macOS,variant=Mac Catalyst' CODE_SIGNING_ALLOWED=NO -derivedDataPath "$W/dd" build | grep -E "error:|BUILD (SUCCEEDED|FAILED)"
APP="$W/dd/Build/Products/Debug-maccatalyst/Sweep.app"
codesign -s - --force --deep "$APP" 2>/dev/null
"$APP/Contents/MacOS/Sweep" "$@" > "$W/run.log" 2>&1 &
echo "launched; log at $W/run.log"
