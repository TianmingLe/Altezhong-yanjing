# Known Issues

## Firmware build warnings (accepted for MVP)

### `CONFIG_BT_BTC_TASK_STACK_SIZE` macro redefined

- Symptom: build logs include warnings like:
  - `"CONFIG_BT_BTC_TASK_STACK_SIZE" redefined`
- Source: ESP-IDF/SDK `sdkconfig.h` defines this macro and PlatformIO `build_flags` may override it for Arduino BLE stack compatibility.
- Decision: accepted for MVP because it is not introduced by Phase 2 (BLE audio optimization) changes and eliminating it requires SDK/toolchain/config refactors beyond current scope.

### `esp32-camera` deprecated pin fields

- Symptom: warnings like:
  - `pin_sscb_sda is deprecated: please use pin_sccb_sda instead`
  - `pin_sscb_scl is deprecated: please use pin_sccb_scl instead`
- Source: `esp32-camera` API deprecation; upstream library change required to fully eliminate warnings.
- Decision: accepted for MVP.

