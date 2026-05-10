#ifndef EV_DRIVE_CORE_H
#define EV_DRIVE_CORE_H

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    EV_DRIVE_ECO = 0,
    EV_DRIVE_NORMAL = 1,
    EV_DRIVE_SPORT = 2,
    EV_DRIVE_REVERSE = 3
} EvDriveMode;

typedef enum {
    EV_LINK_DUAL_LINK = 0,
    EV_LINK_CAN_PRIMARY = 1,
    EV_LINK_CAN_ONLY_SAFE = 2
} EvLinkMode;

typedef struct {
    float max_speed_kmh;
    float max_acceleration_ms2;
    float max_deceleration_ms2; /* negative value in Python model */
    float max_power_kw;
    float regen_max_current_a;
    float speed_zero_threshold_kmh;
    float drive_mode_multiplier_eco;
    float drive_mode_multiplier_normal;
    float drive_mode_multiplier_sport;
    float drive_mode_multiplier_reverse;
} EvDriveConfig;

typedef struct {
    float speed_kmh;
    float acceleration_ms2;
    float power_kw;
    float energy_consumption_kwh;
} EvDriveState;

typedef struct {
    float max_speed_kmh;
    float max_acceleration_ms2;
    float max_power_kw;
} EvDriveLimits;

typedef struct {
    float target_duty_cycle;   /* 0..1 */
    float regen_current_a;     /* <=0 for braking */
    float requested_power_kw;
} EvActuatorCommand;

float ev_clampf(float value, float min_value, float max_value);

EvDriveLimits ev_get_drive_mode_limits(const EvDriveConfig* config, EvDriveMode mode);

EvActuatorCommand ev_apply_throttle(
    EvDriveState* state,
    const EvDriveConfig* config,
    EvDriveMode mode,
    float throttle_percent,
    float dt_s
);

EvActuatorCommand ev_apply_brake(
    EvDriveState* state,
    const EvDriveConfig* config,
    float brake_percent,
    float dt_s
);

EvLinkMode ev_select_link_mode(
    int prefer_lorawan,
    float can_heartbeat_age_s,
    float lora_heartbeat_age_s,
    float lora_rssi_dbm,
    float heartbeat_timeout_s,
    float lora_min_rssi_dbm
);

#ifdef __cplusplus
}
#endif

#endif /* EV_DRIVE_CORE_H */
