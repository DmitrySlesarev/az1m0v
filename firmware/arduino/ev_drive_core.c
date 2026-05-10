#include "ev_drive_core.h"

static float mode_multiplier(const EvDriveConfig* config, EvDriveMode mode) {
    if (!config) {
        return 1.0f;
    }
    switch (mode) {
        case EV_DRIVE_ECO:
            return config->drive_mode_multiplier_eco;
        case EV_DRIVE_SPORT:
            return config->drive_mode_multiplier_sport;
        case EV_DRIVE_REVERSE:
            return config->drive_mode_multiplier_reverse;
        case EV_DRIVE_NORMAL:
        default:
            return config->drive_mode_multiplier_normal;
    }
}

float ev_clampf(float value, float min_value, float max_value) {
    if (value < min_value) {
        return min_value;
    }
    if (value > max_value) {
        return max_value;
    }
    return value;
}

EvDriveLimits ev_get_drive_mode_limits(const EvDriveConfig* config, EvDriveMode mode) {
    EvDriveLimits limits = {0.0f, 0.0f, 0.0f};
    if (!config) {
        return limits;
    }

    float mult = mode_multiplier(config, mode);
    limits.max_speed_kmh = config->max_speed_kmh * mult;
    limits.max_acceleration_ms2 = config->max_acceleration_ms2 * mult;
    limits.max_power_kw = config->max_power_kw * mult;
    return limits;
}

static void integrate_speed(EvDriveState* state, float speed_limit_kmh, float speed_zero_threshold_kmh, float dt_s) {
    if (!state || dt_s <= 0.0f) {
        return;
    }

    float speed_ms = state->speed_kmh / 3.6f;
    speed_ms += state->acceleration_ms2 * dt_s;

    if (speed_ms < 0.0f) {
        speed_ms = 0.0f;
    }
    {
        float max_speed_ms = speed_limit_kmh / 3.6f;
        if (speed_ms > max_speed_ms) {
            speed_ms = max_speed_ms;
        }
    }

    state->speed_kmh = speed_ms * 3.6f;
    if (state->speed_kmh < speed_zero_threshold_kmh) {
        state->speed_kmh = 0.0f;
        state->acceleration_ms2 = 0.0f;
    }
}

EvActuatorCommand ev_apply_throttle(
    EvDriveState* state,
    const EvDriveConfig* config,
    EvDriveMode mode,
    float throttle_percent,
    float dt_s
) {
    EvActuatorCommand command = {0.0f, 0.0f, 0.0f};
    if (!state || !config) {
        return command;
    }

    EvDriveLimits limits = ev_get_drive_mode_limits(config, mode);
    float throttle = ev_clampf(throttle_percent, 0.0f, 100.0f) / 100.0f;

    state->acceleration_ms2 = limits.max_acceleration_ms2 * throttle;
    state->power_kw = limits.max_power_kw * throttle;
    command.target_duty_cycle = throttle;
    command.requested_power_kw = state->power_kw;
    command.regen_current_a = 0.0f;

    integrate_speed(state, limits.max_speed_kmh, config->speed_zero_threshold_kmh, dt_s);
    if (state->power_kw > 0.0f) {
        state->energy_consumption_kwh += (state->power_kw * dt_s) / 3600.0f;
    }
    return command;
}

EvActuatorCommand ev_apply_brake(
    EvDriveState* state,
    const EvDriveConfig* config,
    float brake_percent,
    float dt_s
) {
    EvActuatorCommand command = {0.0f, 0.0f, 0.0f};
    if (!state || !config) {
        return command;
    }

    float brake = ev_clampf(brake_percent, 0.0f, 100.0f) / 100.0f;
    float max_decel = config->max_deceleration_ms2;
    if (max_decel > 0.0f) {
        max_decel = -max_decel;
    }

    state->acceleration_ms2 = max_decel * brake;
    state->power_kw = 0.0f;
    command.target_duty_cycle = 0.0f;
    command.regen_current_a = -(config->regen_max_current_a * brake);
    command.requested_power_kw = 0.0f;

    integrate_speed(state, config->max_speed_kmh, config->speed_zero_threshold_kmh, dt_s);
    return command;
}

EvLinkMode ev_select_link_mode(
    int prefer_lorawan,
    float can_heartbeat_age_s,
    float lora_heartbeat_age_s,
    float lora_rssi_dbm,
    float heartbeat_timeout_s,
    float lora_min_rssi_dbm
) {
    int can_healthy = can_heartbeat_age_s <= (heartbeat_timeout_s * 2.0f);
    int lora_healthy = lora_heartbeat_age_s <= heartbeat_timeout_s && lora_rssi_dbm >= lora_min_rssi_dbm;

    if (prefer_lorawan && can_healthy && lora_healthy) {
        return EV_LINK_DUAL_LINK;
    }
    if (can_healthy) {
        return EV_LINK_CAN_PRIMARY;
    }
    return EV_LINK_CAN_ONLY_SAFE;
}
