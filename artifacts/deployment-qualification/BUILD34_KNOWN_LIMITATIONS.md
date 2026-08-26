# BUILD 34 Known Limitations

- single-machine local deployment qualification only
- no production cloud infrastructure or external release registry
- Windows-native service supervision via fixture supervisor only
- container packaging not canonical — repository is Windows-native dev
- no external secret manager configured by default
- Mongo migration/backup path fixture-tested when IMP_TEST_MONGODB_URI unavailable
- no blue/green or rolling multi-instance deployment
- no actual supervised-live environment promotion executed against real broker
- deployment canary defaults to zero real orders — fixture qualification only
- no autonomous live trading authority added by BUILD 34
- human session authorization and per-order confirmation remain mandatory
