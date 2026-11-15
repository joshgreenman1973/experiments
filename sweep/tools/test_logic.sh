#!/bin/sh
# Compile the app's non-UI files with the test harness and run it on this Mac.
cd "$(dirname "$0")/.." && mkdir -p tools/tests/build &&
swiftc -O -o tools/tests/build/logic ios/Sweep/Model.swift ios/Sweep/SignData.swift ios/Sweep/Schedule.swift ios/Sweep/Holidays.swift tools/tests/main.swift &&
tools/tests/build/logic ios/Sweep/Data
