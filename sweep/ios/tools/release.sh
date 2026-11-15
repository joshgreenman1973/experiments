#!/bin/sh
# Archive, export and upload Sweep to App Store Connect (TestFlight). Run from ios/.
set -e
cd "$(dirname "$0")/.."
U=$(cat profile_uuid.txt)
rm -rf build/Sweep.xcarchive build/export
xcodebuild -project Sweep.xcodeproj -scheme Sweep -configuration Release -destination 'generic/platform=iOS' \
  -archivePath build/Sweep.xcarchive archive \
  CODE_SIGN_STYLE=Manual CODE_SIGN_IDENTITY="Apple Distribution: Josh Greenman (2JVR7UX89N)" \
  PROVISIONING_PROFILE_SPECIFIER="$U" DEVELOPMENT_TEAM=2JVR7UX89N | grep -E "error:|warning: .*Sweep/|ARCHIVE|archive build number"
xcodebuild -exportArchive -archivePath build/Sweep.xcarchive -exportPath build/export -exportOptionsPlist ExportOptions.plist | grep -E "error|EXPORT"
if [ "$1" = "--upload" ]; then
  xcrun altool --upload-app -f build/export/Sweep.ipa -t ios --apiKey ZRL2ZT22XY --apiIssuer cd73ce4b-4549-4afb-ab2f-ec1d8c5fab7a
fi
