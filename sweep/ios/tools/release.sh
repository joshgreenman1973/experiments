#!/bin/sh
# Archive, export and upload Sweep to App Store Connect (TestFlight). Run from ios/.
set -e
cd "$(dirname "$0")/.."
U=$(cat profile_uuid.txt)
WU=$(cat widget_profile_uuid.txt)
# One build number for the app and the widget (they must match): minutes since the Unix epoch,
# always increasing and inside Apple's 32-bit limit.
BUILD=$(( $(date -u +%s) / 60 ))
rm -rf build/Sweep.xcarchive build/export
xcodebuild -project Sweep.xcodeproj -scheme Sweep -configuration Release -destination 'generic/platform=iOS' \
  -archivePath build/Sweep.xcarchive archive \
  CODE_SIGN_STYLE=Manual CODE_SIGN_IDENTITY="Apple Distribution: Josh Greenman (2JVR7UX89N)" \
  SWEEP_APP_PROFILE="$U" SWEEP_WIDGET_PROFILE="$WU" CURRENT_PROJECT_VERSION=$BUILD DEVELOPMENT_TEAM=2JVR7UX89N \
  | grep -E "error:|warning: .*Sweep(Widget|Shared)?/|ARCHIVE"
echo "build $BUILD"
xcodebuild -exportArchive -archivePath build/Sweep.xcarchive -exportPath build/export -exportOptionsPlist ExportOptions.plist | grep -E "error|EXPORT"
if [ "$1" = "--upload" ]; then
  xcrun altool --upload-app -f build/export/Sweep.ipa -t ios --apiKey ZRL2ZT22XY --apiIssuer cd73ce4b-4549-4afb-ab2f-ec1d8c5fab7a
fi
