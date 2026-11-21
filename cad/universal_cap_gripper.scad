// ============================================================================
// HydroCap: Ultra-Thin Waterproof Universal Bottle-Cap Hydration Tracker CAD
// Parametric OpenSCAD Design (Supports 26-65 mm or 26-45 mm Screw Caps)
// Includes IP67 Side USB-C Bezel, Captive TPU Plug, O-Ring Seal & M2 Bosses
// ============================================================================

CAP_PRESET  = "universal_65";   // "universal_65" (26-65 mm) | "compact_45" (26-45 mm)
LOAD_STAGE  = "flexure_3spoke"; // "flexure_3spoke" (0.8 mm SS) | "fx29_yoke" (TE FX29 I2C)
VIEW_MODE   = "assembled";      // "assembled" | "exploded" | "print_plate"

CAP_OD_MIN    = 26.0;
CAP_OD_MAX    = (CAP_PRESET == "universal_65") ? 65.0 : 45.0;
PUCK_OD       = (CAP_PRESET == "universal_65") ? 72.0 : 54.0;
CHUCK_BASE_H  = 5.2;
FLEXURE_THICK = (LOAD_STAGE == "flexure_3spoke") ? 0.8 : 5.2;
HARDSTOP_GAP  = 0.35;
PCB_OD        = 42.0;   // Ø42 mm 0.8 mm PCBWay V2 board
PCB_THICK     = 0.8;
LIPO_L        = 30.0;
LIPO_W        = 20.0;
LIPO_H        = 3.2;    // 302030 150 mAh LiPo pouch
TOP_COVER_H   = 2.2;
ORING_ID      = 58.0;   // Radial nitrile/silicone O-ring (58 x 1.5 mm)

$fn = 72;

module ring(od, id, h) {
    difference() {
        cylinder(d = od, h = h);
        translate([0, 0, -0.5]) cylinder(d = id, h = h + 1.0);
    }
}

module scroll_collar() {
    color("#34495E")
    difference() {
        union() {
            ring(PUCK_OD, CAP_OD_MAX + 3.0, CHUCK_BASE_H);
            for (i = [0 : 35]) {
                rotate([0, 0, i * 10])
                    translate([PUCK_OD / 2 - 0.3, -0.8, 0.4])
                        cube([0.8, 1.6, CHUCK_BASE_H - 0.8]);
            }
        }
        translate([0, 0, CHUCK_BASE_H - 1.4])
            ring(CAP_OD_MAX + 5.2, CAP_OD_MAX + 2.8, 1.6);
    }
}

module gripper_jaw(r_engage) {
    jaw_len = (PUCK_OD / 2) - (CAP_OD_MIN / 2) - 2.0;
    translate([r_engage, 0, 0]) {
        color("#2C3E50")
        translate([0, -5.0, 0.5])
            cube([jaw_len, 10.0, CHUCK_BASE_H - 1.2]);
        color("#E67E22")
        translate([-1.6, -4.4, 0.7])
            cube([2.0, 8.8, CHUCK_BASE_H - 1.6]);
    }
}

module chuck_hub_plate() {
    color("#5D6D7E")
    difference() {
        cylinder(d = CAP_OD_MAX + 2.4, h = 2.0);
        for (k = [0 : 2]) {
            rotate([0, 0, k * 120])
                translate([CAP_OD_MIN / 2, -5.4, -0.5])
                    cube([(CAP_OD_MAX - CAP_OD_MIN) / 2 + 2.0, 10.8, 3.0]);
        }
        // Central RTV-potted strain-bridge wire gland
        translate([0, 0, -0.5]) cylinder(d = 4.0, h = 3.0);
    }
}

module three_spoke_flexure() {
    outer_od = PUCK_OD - 6.0;
    outer_id = outer_od - 8.0;
    hub_od   = 22.0;
    spoke_w  = 6.5;
    color("#BDC3C7")
    union() {
        ring(outer_od, outer_id, 0.8);
        cylinder(d = hub_od, h = 0.8);
        for (k = [0 : 2]) {
            rotate([0, 0, k * 120])
                translate([hub_od / 2 - 1.5, -spoke_w / 2, 0])
                    cube([(outer_id - hub_od) / 2 + 2.5, spoke_w, 0.8]);
        }
    }
}

module fx29_reverse_yoke() {
    color("#95A5A6")
    difference() {
        cylinder(d = 26.0, h = 5.2);
        translate([0, 0, 1.0]) cylinder(d = 20.2, h = 4.5);
    }
    color("#D4AC0D")
    translate([0, 0, 1.0]) cylinder(d = 19.7, h = 4.2);
}

module electronics_puck() {
    puck_h = 5.6;
    color("#1F618D")
    difference() {
        cylinder(d = PUCK_OD, h = puck_h);
        // Cavity for 302030 LiPo + Ø42 mm PCB
        translate([0, 0, 1.2]) cylinder(d = PCB_OD + 1.4, h = puck_h);
        // Radial O-ring seal groove (Ø58 x 1.5 mm)
        translate([0, 0, puck_h - 1.4]) ring(ORING_ID + 1.8, ORING_ID - 1.4, 1.6);
        // IP67 Side USB-C receptacle bezel cutout (9.6 x 4.0 mm) at -Y perimeter
        translate([-4.8, -PUCK_OD / 2 - 1.0, 2.0]) cube([9.6, 16.0, 3.8]);
        // 4x M2 brass heat-set insert bosses
        for (pt = [[-15.5, 9.0], [15.5, 9.0], [-14.5, -10.5], [14.5, -10.5]]) {
            translate([pt[0], pt[1], 0.8]) cylinder(d = 3.2, h = puck_h);
        }
    }
    // 302030 150 mAh LiPo battery
    color("#F39C12")
    translate([-LIPO_L / 2, -LIPO_W / 2, 1.3]) cube([LIPO_L, LIPO_W, LIPO_H]);
    // Ø42 mm Circular V2 PCBWay PCB
    color("#0B5345")
    translate([0, 0, 4.6]) cylinder(d = PCB_OD, h = PCB_THICK);
}

// Captive TPU 85A IP67 USB-C plug
module usbc_tpu_plug() {
    color("#E74C3C")
    translate([-4.6, -PUCK_OD / 2 - 1.2, 2.1]) {
        cube([9.2, 3.0, 3.6]);
        translate([1.4, 2.5, 0.5]) cube([6.4, 4.0, 2.4]); // Tongue insert
    }
}

module top_lid_and_bail() {
    color("#2980B9")
    difference() {
        cylinder(d = PUCK_OD, h = TOP_COVER_H);
        translate([0, 0, 0.8]) ring(PUCK_OD + 1.0, PUCK_OD - 6.0, TOP_COVER_H);
        // 4x M2 countersunk fastener holes
        for (pt = [[-15.5, 9.0], [15.5, 9.0], [-14.5, -10.5], [14.5, -10.5]]) {
            translate([pt[0], pt[1], -0.5]) cylinder(d = 2.2, h = TOP_COVER_H + 1.0);
        }
    }
    color("#D0D3D4")
    translate([0, 0, 0.9])
        difference() {
            ring(PUCK_OD - 0.4, PUCK_OD - 5.2, 1.3);
            translate([-PUCK_OD, -PUCK_OD / 2, -0.5]) cube([PUCK_OD, PUCK_OD, 2.5]);
        }
}

module full_assembly(z_gap = 0.0) {
    jaw_r = 16.0;
    scroll_collar();
    for (k = [0 : 2]) rotate([0, 0, k * 120]) gripper_jaw(jaw_r);
    translate([0, 0, CHUCK_BASE_H]) chuck_hub_plate();

    translate([0, 0, CHUCK_BASE_H + 2.0 + z_gap]) {
        if (LOAD_STAGE == "flexure_3spoke") three_spoke_flexure();
        else fx29_reverse_yoke();
    }

    z_puck = CHUCK_BASE_H + 2.0 + FLEXURE_THICK + HARDSTOP_GAP + 2 * z_gap;
    translate([0, 0, z_puck]) {
        electronics_puck();
        usbc_tpu_plug();
    }
    translate([0, 0, z_puck + 5.6 + z_gap]) top_lid_and_bail();
}

if (VIEW_MODE == "assembled") full_assembly(0.0);
else if (VIEW_MODE == "exploded") full_assembly(10.0);
else {
    scroll_collar();
    translate([PUCK_OD + 8, 0, 0]) chuck_hub_plate();
    translate([-PUCK_OD - 8, 0, 0]) top_lid_and_bail();
    translate([0, -PUCK_OD / 2 - 14, 0]) usbc_tpu_plug();
    for (k = [0 : 2]) translate([0, PUCK_OD / 2 + 12 + k * 14, 0]) gripper_jaw(0);
}
