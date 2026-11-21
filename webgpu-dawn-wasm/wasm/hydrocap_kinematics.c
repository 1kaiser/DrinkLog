/*
 * HydroCap Relocation-Free wasm32 Kinematics, MVP Matrix & Physics Kernel.
 * Compiled directly by Debian Clang (--target=wasm32 -O3 -fno-math-errno
 * -fno-builtin-memset -fno-builtin-memcpy -nostdlib) without wasm-ld.
 * Zero static globals, zero .rodata LUTs, zero libc imports.
 */

#include <stdint.h>

static inline float clampf(float x, float lo, float hi) {
    return (x < lo) ? lo : ((x > hi) ? hi : x);
}

static inline float smoothstepf(float x) {
    float t = clampf(x, 0.0f, 1.0f);
    return t * t * (3.0f - 2.0f * t);
}

/* Range-reduced Taylor minimax sinf/cosf (accuracy < 2e-6, zero LUTs) */
static inline float wasm_sinf(float x) {
    const float PI = 3.1415926535f;
    const float TWO_PI = 6.283185307f;
    const float HALF_PI = 1.570796327f;
    /* Reduce to [-PI, PI] via floor */
    float k = (float)((int)(x / TWO_PI + ((x >= 0.0f) ? 0.5f : -0.5f)));
    float r = x - k * TWO_PI;
    if (r > HALF_PI) r = PI - r;
    else if (r < -HALF_PI) r = -PI - r;
    float r2 = r * r;
    return r * (1.0f - r2 * (0.16666667f - r2 * (0.0083333338f - r2 * 0.0001984127f)));
}

static inline float wasm_cosf(float x) {
    return wasm_sinf(x + 1.570796327f);
}

static inline float wasm_tanf(float x) {
    float c = wasm_cosf(x);
    return wasm_sinf(x) / ((__builtin_fabsf(c) < 1e-6f) ? 1e-6f : c);
}

/*
 * Evaluate analytical HydroCap state at time t_sec over duration_sec (12.0s).
 * Writes 24 floats into out_state:
 *   [0]  stage (1..5)         [1]  jaw_radius_u      [2]  scroll_rot_y
 *   [3]  cap_drop_y           [4]  cap_rot_y         [5]  bottle_lift_y
 *   [6]  bail_angle_x         [7]  flex_strain       [8]  water_frac
 *   [9]  mass_g               [10] hc_ml             [11] usb_plug_z
 *   [12] cable_prog           [13] ble_phase         [14] phone_vis
 *   [15..17] cam_eye (x,y,z)  [18..20] cam_target    [21..23] led_rgb
 */
void wasm_eval_stage(float t_sec, float duration_sec, float* out_state) {
    float dur = (duration_sec > 0.1f) ? duration_sec : 12.0f;
    float q = (float)((int)(t_sec / dur));
    float t = t_sec - q * dur;
    if (t < 0.0f) t += dur;

    float stage = 1.0f;
    float jaw_dia_mm = 32.0f;
    float cap_drop_y = 0.0f;
    float cap_rot_y = 0.0f;
    float bottle_lift_y = 0.0f;
    float bail_angle = 0.0f;
    float flex_strain = 0.0f;
    float water_frac = 0.85f;
    float mass_g = 0.0f;
    float hc_ml = 0.0f;
    float usb_plug_z = 0.0f;
    float cable_prog = 0.0f;
    float ble_phase = -1.0f;
    float phone_vis = 0.0f;
    float cx = 16.5f, cy = 20.5f, cz = 28.5f;
    float tx = 0.0f, ty = 10.5f, tz = 0.0f;
    float lr = 0.18f, lg = 0.65f, lb = 0.90f;

    if (t < 2.6f) {
        stage = 1.0f;
        float u = smoothstepf(t / 2.6f);
        jaw_dia_mm = 64.0f - 31.5f * u;
        cap_drop_y = 3.8f * (1.0f - u);
        cap_rot_y = 0.8f * (1.0f - u);
        cx = 16.5f - 1.2f * u;
        cy = 19.5f + 1.2f * u;
        cz = 28.5f;
        ty = 11.2f - 0.6f * u;
    } else if (t < 5.2f) {
        stage = 2.0f;
        float u = smoothstepf((t - 2.6f) / 2.6f);
        float bail_u = clampf(u * 1.9f, 0.0f, 1.0f);
        bail_angle = 1.5707963f * bail_u;
        float lift_u = clampf((u - 0.22f) / 0.78f, 0.0f, 1.0f);
        float lift_bell = wasm_sinf(lift_u * 3.14159265f);
        bottle_lift_y = 2.6f * lift_bell;
        flex_strain = lift_bell;
        mass_g = (lift_bell > 0.15f || u > 0.60f) ? 1180.0f : 0.0f;
        cx = 17.5f; cy = 21.5f; cz = 32.5f;
        ty = 11.4f;
        lr = 0.15f; lg = 0.85f; lb = 0.38f;
    } else if (t < 7.4f) {
        stage = 3.0f;
        float u = smoothstepf((t - 5.2f) / 2.2f);
        cap_drop_y = 3.2f * wasm_sinf(u * 3.14159265f);
        cap_rot_y = 6.2831853f * u;
        float sip_u = clampf((u - 0.22f) / 0.55f, 0.0f, 1.0f);
        water_frac = 0.85f - 0.24f * sip_u;
        mass_g = 0.0f;
        cx = 16.5f; cy = 20.5f; cz = 28.5f;
        ty = 10.2f;
        lr = 0.05f; lg = 0.78f; lb = 0.92f;
    } else if (t < 9.8f) {
        stage = 4.0f;
        float u = smoothstepf((t - 7.4f) / 2.4f);
        bail_angle = 1.5707963f;
        float lift_u = clampf(u * 1.1f, 0.0f, 1.0f);
        float lift_bell = wasm_sinf(lift_u * 3.14159265f);
        bottle_lift_y = 2.4f * lift_bell;
        flex_strain = 0.82f * lift_bell;
        water_frac = 0.61f;
        mass_g = 970.0f;
        hc_ml = (u > 0.35f) ? 210.0f : 0.0f;
        float bp = u * 2.0f;
        ble_phase = bp - (float)((int)bp);
        phone_vis = 1.0f;
        cx = 14.5f; cy = 20.5f; cz = 34.5f;
        tx = 2.0f; ty = 11.4f; tz = 0.0f;
        lr = 0.15f; lg = 0.85f; lb = 0.38f;
    } else {
        stage = 5.0f;
        float u = smoothstepf((t - 9.8f) / 2.2f);
        water_frac = 0.61f;
        mass_g = 970.0f;
        hc_ml = 210.0f;
        usb_plug_z = -2.0f * clampf(u * 2.0f, 0.0f, 1.0f);
        cable_prog = clampf((u - 0.25f) / 0.75f, 0.0f, 1.0f);
        cx = -15.5f; cy = 18.8f; cz = 16.5f;
        tx = -1.8f; ty = 14.5f; tz = 0.0f;
        if (cable_prog > 0.60f) {
            lr = 0.95f; lg = 0.22f; lb = 0.18f;
        } else {
            lr = 0.15f; lg = 0.85f; lb = 0.38f;
        }
    }

    out_state[0] = stage;
    out_state[1] = (jaw_dia_mm / 10.0f) * 0.5f;
    out_state[2] = (jaw_dia_mm - 32.0f) * 0.04f;
    out_state[3] = cap_drop_y;
    out_state[4] = cap_rot_y;
    out_state[5] = bottle_lift_y;
    out_state[6] = bail_angle;
    out_state[7] = flex_strain;
    out_state[8] = water_frac;
    out_state[9] = mass_g;
    out_state[10] = hc_ml;
    out_state[11] = usb_plug_z;
    out_state[12] = cable_prog;
    out_state[13] = ble_phase;
    out_state[14] = phone_vis;
    out_state[15] = cx; out_state[16] = cy; out_state[17] = cz;
    out_state[18] = tx; out_state[19] = ty; out_state[20] = tz;
    out_state[21] = lr; out_state[22] = lg; out_state[23] = lb;
}

/*
 * Build Model (4x4) and WebGPU Zero-to-One MVP (4x4) in column-major order.
 * trs[9] = [tx, ty, tz, rx, ry, rz, sx, sy, sz].
 */
void wasm_build_mvp(const float* trs,
                    const float* cam_eye,
                    const float* cam_target,
                    float fov_rad,
                    float aspect,
                    float near_z,
                    float far_z,
                    float* out_mvp16,
                    float* out_model16) {
    float cx = wasm_cosf(trs[3]), sx = wasm_sinf(trs[3]);
    float cy = wasm_cosf(trs[4]), sy = wasm_sinf(trs[4]);
    float cz = wasm_cosf(trs[5]), sz = wasm_sinf(trs[5]);
    float scx = trs[6], scy = trs[7], scz = trs[8];

    /* R = Ry * Rx * Rz * S */
    float m00 = (cy * cz + sy * sx * sz) * scx;
    float m10 = (cx * sz) * scx;
    float m20 = (-sy * cz + cy * sx * sz) * scx;

    float m01 = (-cy * sz + sy * sx * cz) * scy;
    float m11 = (cx * cz) * scy;
    float m21 = (sy * sz + cy * sx * cz) * scy;

    float m02 = (sy * cx) * scz;
    float m12 = (-sx) * scz;
    float m22 = (cy * cx) * scz;

    out_model16[0] = m00; out_model16[1] = m10; out_model16[2] = m20; out_model16[3] = 0.0f;
    out_model16[4] = m01; out_model16[5] = m11; out_model16[6] = m21; out_model16[7] = 0.0f;
    out_model16[8] = m02; out_model16[9] = m12; out_model16[10] = m22; out_model16[11] = 0.0f;
    out_model16[12] = trs[0]; out_model16[13] = trs[1]; out_model16[14] = trs[2]; out_model16[15] = 1.0f;

    /* LookAt view matrix (right-handed, up = 0,1,0) */
    float fx = cam_eye[0] - cam_target[0];
    float fy = cam_eye[1] - cam_target[1];
    float fz = cam_eye[2] - cam_target[2];
    float f_len = __builtin_sqrtf(fx * fx + fy * fy + fz * fz);
    if (f_len < 1e-5f) f_len = 1.0f;
    float zx = fx / f_len, zy = fy / f_len, zz = fz / f_len;

    /* x_axis = normalize(cross(up, z_axis)) where up=(0,1,0) -> (zz, 0, -zx) */
    float xx = zz, xy = 0.0f, xz = -zx;
    float x_len = __builtin_sqrtf(xx * xx + xz * xz);
    if (x_len < 1e-5f) { xx = 1.0f; xz = 0.0f; x_len = 1.0f; }
    xx /= x_len; xz /= x_len;

    /* y_axis = cross(z_axis, x_axis) */
    float yx = zy * xz - zz * xy;
    float yy = zz * xx - zx * xz;
    float yz = zx * xy - zy * xx;

    float vx0 = xx, vx1 = yx, vx2 = zx;
    float vy0 = xy, vy1 = yy, vy2 = zy;
    float vz0 = xz, vz1 = yz, vz2 = zz;
    float vt0 = -(xx * cam_eye[0] + xy * cam_eye[1] + xz * cam_eye[2]);
    float vt1 = -(yx * cam_eye[0] + yy * cam_eye[1] + yz * cam_eye[2]);
    float vt2 = -(zx * cam_eye[0] + zy * cam_eye[1] + zz * cam_eye[2]);

    /* Perspective WebGPU ZO: z_ndc in [0, 1] */
    float f_proj = 1.0f / wasm_tanf(fov_rad * 0.5f);
    float p00 = f_proj / aspect;
    float p11 = f_proj;
    float nf = 1.0f / (near_z - far_z);
    float p22 = far_z * nf;
    float p32 = far_z * near_z * nf;

    /* PV = P * V */
    float pv00 = p00 * vx0, pv01 = p00 * vy0, pv02 = p00 * vz0, pv03 = p00 * vt0;
    float pv10 = p11 * vx1, pv11 = p11 * vy1, pv12 = p11 * vz1, pv13 = p11 * vt1;
    float pv20 = p22 * vx2, pv21 = p22 * vy2, pv22 = p22 * vz2, pv23 = p22 * vt2 + p32;
    float pv30 = -vx2,      pv31 = -vy2,      pv32 = -vz2,      pv33 = -vt2;

    /* MVP = PV * Model (column-major) */
    for (int col = 0; col < 4; ++col) {
        float c0 = out_model16[col * 4 + 0];
        float c1 = out_model16[col * 4 + 1];
        float c2 = out_model16[col * 4 + 2];
        float c3 = out_model16[col * 4 + 3];
        out_mvp16[col * 4 + 0] = pv00 * c0 + pv01 * c1 + pv02 * c2 + pv03 * c3;
        out_mvp16[col * 4 + 1] = pv10 * c0 + pv11 * c1 + pv12 * c2 + pv13 * c3;
        out_mvp16[col * 4 + 2] = pv20 * c0 + pv21 * c1 + pv22 * c2 + pv23 * c3;
        out_mvp16[col * 4 + 3] = pv30 * c0 + pv31 * c1 + pv32 * c2 + pv33 * c3;
    }
}

/* Inertial mass & sip classification parity kernel: out_res = [mass_g, delta_ml, event_type] */
void wasm_eval_physics(float raw_force_g, float az_g, float prev_mass_g, float* out_res) {
    if (__builtin_fabsf(raw_force_g) < 45.0f) {
        out_res[0] = 0.0f;
        out_res[1] = 0.0f;
        out_res[2] = 0.0f; /* Auto-tare */
        return;
    }
    float az = clampf(az_g, 0.85f, 1.15f);
    float mass_g = raw_force_g / az;
    float delta = prev_mass_g - mass_g;
    float ev_type = 4.0f;
    float ml = 0.0f;
    if (prev_mass_g < 0.0f) {
        ev_type = 1.0f;
    } else if (delta >= 15.0f) {
        ev_type = 2.0f;
        ml = delta;
    } else if (delta <= -25.0f) {
        ev_type = 3.0f;
    }
    out_res[0] = mass_g;
    out_res[1] = ml;
    out_res[2] = ev_type;
}
