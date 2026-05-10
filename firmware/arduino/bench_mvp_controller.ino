#include <Arduino.h>
#include "ev_drive_core.h"

/*
 * bench_mvp_controller.ino
 *
 * Minimal Arduino sketch for the current az1m0v bench MVP.
 * - Uses C core functions ported from Python vehicle controller logic
 * - Emits one-line JSON messages for Raspberry Pi bench_mvp bridge
 * - Supports manual command input over USB serial:
 *     THROTTLE:<0-100>
 *     BRAKE:<0-100>
 */

static EvDriveConfig g_cfg = {
    120.0f, /* max_speed_kmh */
    3.0f,   /* max_acceleration_ms2 */
    -5.0f,  /* max_deceleration_ms2 */
    150.0f, /* max_power_kw */
    50.0f,  /* regen_max_current_a */
    0.1f,   /* speed_zero_threshold_kmh */
    0.7f,   /* eco */
    1.0f,   /* normal */
    1.2f,   /* sport */
    1.0f    /* reverse */
};

static EvDriveState g_state = {0.0f, 0.0f, 0.0f, 0.0f};
static unsigned long g_last_ms = 0;
static float g_last_throttle = 0.0f;
static float g_last_brake = 0.0f;

static void emit_battery_status(void) {
    const float sim_soc = 75.0f - (g_state.energy_consumption_kwh * 0.2f);
    const float sim_current = g_state.power_kw > 0.0f ? (g_state.power_kw * 1000.0f) / 392.0f : 0.0f;
    Serial.print("{\"kind\":\"battery_status\",\"voltage\":392.0,\"current\":");
    Serial.print(sim_current, 2);
    Serial.print(",\"temperature\":31.0,\"soc\":");
    Serial.print(sim_soc, 2);
    Serial.println("}");
}

static void emit_motor_status(const EvActuatorCommand* cmd) {
    const float rpm = g_state.speed_kmh * 48.0f;
    const float torque = cmd ? (cmd->requested_power_kw * 6.0f) : 0.0f;
    Serial.print("{\"kind\":\"motor_status\",\"speed_rpm\":");
    Serial.print(rpm, 2);
    Serial.print(",\"torque_nm\":");
    Serial.print(torque, 2);
    Serial.print(",\"temperature_c\":46.0}");
    Serial.println();
}

static void emit_vehicle_status(EvDriveMode mode) {
    const char* mode_name = "normal";
    if (mode == EV_DRIVE_ECO) {
        mode_name = "eco";
    } else if (mode == EV_DRIVE_SPORT) {
        mode_name = "sport";
    } else if (mode == EV_DRIVE_REVERSE) {
        mode_name = "reverse";
    }

    Serial.print("{\"kind\":\"vehicle_status\",\"state\":\"driving\",\"speed_kmh\":");
    Serial.print(g_state.speed_kmh, 2);
    Serial.print(",\"drive_mode\":\"");
    Serial.print(mode_name);
    Serial.print("\",\"power_kw\":");
    Serial.print(g_state.power_kw, 2);
    Serial.println("}");
}

static float parse_value(const String& line, const char* prefix) {
    const int prefix_len = strlen(prefix);
    if (!line.startsWith(prefix)) {
        return -1.0f;
    }
    return line.substring(prefix_len).toFloat();
}

void setup() {
    Serial.begin(115200);
    g_last_ms = millis();
}

void loop() {
    unsigned long now_ms = millis();
    float dt_s = (now_ms - g_last_ms) / 1000.0f;
    if (dt_s <= 0.0f) {
        dt_s = 0.01f;
    }
    g_last_ms = now_ms;

    if (Serial.available() > 0) {
        String line = Serial.readStringUntil('\n');
        line.trim();
        float throttle = parse_value(line, "THROTTLE:");
        float brake = parse_value(line, "BRAKE:");
        if (throttle >= 0.0f) {
            g_last_throttle = throttle;
            g_last_brake = 0.0f;
        } else if (brake >= 0.0f) {
            g_last_brake = brake;
            g_last_throttle = 0.0f;
        }
    }

    EvActuatorCommand cmd;
    if (g_last_brake > 0.0f) {
        cmd = ev_apply_brake(&g_state, &g_cfg, g_last_brake, dt_s);
    } else {
        cmd = ev_apply_throttle(&g_state, &g_cfg, EV_DRIVE_NORMAL, g_last_throttle, dt_s);
    }

    emit_battery_status();
    emit_motor_status(&cmd);
    emit_vehicle_status(EV_DRIVE_NORMAL);
    delay(100);
}
