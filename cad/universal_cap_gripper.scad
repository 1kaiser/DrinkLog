// ============================================================================
// CapHydro: Ultra-Thin Universal Bottle-Cap Hydration Tracker Mechanical CAD
// Parametric OpenSCAD Design (Supports 26-65 mm or 26-45 mm Screw Caps)
// ============================================================================

// --- User-Configurable Parameters ---
CAP_PRESET  = "universal_65";   // "universal_65" (26-65 mm) | "compact_45" (26-45 mm)
LOAD_STAGE  = "flexure_3spoke"; // "flexure_3spoke" (0.8 mm SS) | "fx29_yoke" (TE FX29 I2C)
VIEW_MODE   = "assembled";      // "assembled" | "exploded" | "print_plate"

// Cap clamp travel limits (mm)
CAP_OD_MIN = 26.0;
CAP_OD_MAX = (CAP_PRESET == "universal_65") ? 65.0 : 45.0;
PUCK_OD    = (CAP_PRESET == "universal_65") ? 72.0 : 54.0;

// Vertical stackup heights (mm)
CHUCK_BASE_H     = 5.2;   // Wraps around cap side (0 mm added above cap top!)
CAP_SEAT_Z       = 4.0;   // Top of bottle cap sits inside chuck pocket
FLEXURE_THICK    = (LOAD_STAGE == "flexure_3spoke") ? 0.8 : 5.2;
HARDSTOP_GAP     = 0.35;  // Overload stop gap (protects flexure from drops)
PCB_OD           = 40.0;
PCB_THICK        = 1.0;
LIPO_L           = 30.0;
LIPO_W           = 20.0;
LIPO_H           = 3.2;   // 302030 150 mAh LiPo pouch
TOP_COVER_H      = 2.2;
BAIL_WIRE_D      = 2.6;

$fn = 72;

// ----------------------------------------------------------------------------
// Helper Modules
// ----------------------------------------------------------------------------
module ring(od, id, h) {
    difference() {
        cylinder(d = od, h = h);
        translate([0, 0, -0.5]) cylinder(d = id, h = h + 1.0);
    }
}

// Knurled outer scroll-ring (rotates to drive 3 radial jaws inward)
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
        // Internal lip retaining flange groove
        translate([0, 0, CHUCK_BASE_H - 1.4])
            ring(CAP_OD_MAX + 5.2, CAP_OD_MAX + 2.8, 1.6);
    }
}

// Single gripping jaw with Shore-40A silicone pad & dovetail rail
module gripper_jaw(r_engage) {
    jaw_len = (PUCK_OD / 2) - (CAP_OD_MIN / 2) - 2.0;
    translate([r_engage, 0, 0]) {
        // Rigid PETG/Nylon jaw body
        color("#2C3E50")
        translate([0, -5.0, 0.5])
            cube([jaw_len, 10.0, CHUCK_BASE_H - 1.2]);
        // Shore 40A Silicone high-friction insert
        color("#E67E22")
        translate([-1.6, -4.4, 0.7])
            cube([2.0, 8.8, CHUCK_BASE_H - 1.6]);
    }
}

// Lower hub plate tying the 3 radial jaws to the center load boss
module chuck_hub_plate() {
    color("#5D6D7E")
    difference() {
        cylinder(d = CAP_OD_MAX + 2.4, h = 2.0);
        // 3 radial guide slots
        for (k = [0 : 2]) {
            rotate([0, 0, k * 120])
                translate([CAP_OD_MIN / 2, -5.4, -0.5])
                    cube([(CAP_OD_MAX - CAP_OD_MIN) / 2 + 2.0, 10.8, 3.0]);
        }
    }
}

// 0.8mm 301-SS 3-spoke 120-deg moment-cancelling planar flexure
module three_spoke_flexure() {
    outer_od = PUCK_OD - 6.0;
    outer_id = outer_od - 8.0;
    hub_od   = 22.0;
    spoke_w  = 6.5;

    color("#BDC3C7")
    union() {
        // Outer lift ring (bonded/bolted to upper puck shell)
        ring(outer_od, outer_id, 0.8);
        // Inner bottle-side boss ring
        cylinder(d = hub_od, h = 0.8);
        // Three 120-deg strain-gauged spokes (4x BF1000-3AA mount here)
        for (k = [0 : 2]) {
            rotate([0, 0, k * 120])
                translate([hub_od / 2 - 1.5, -spoke_w / 2, 0])
                    cube([(outer_id - hub_od) / 2 + 2.5, spoke_w, 0.8]);
        }
    }
}

// Alternative TE FX29 compression load cell inside pull-to-compress reverse yoke
module fx29_reverse_yoke() {
    color("#95A5A6")
    difference() {
        cylinder(d = 26.0, h = 5.2);
        translate([0, 0, 1.0]) cylinder(d = 20.2, h = 4.5);
    }
    // FX29 capsule (19.7 mm OD x 5.0 mm)
    color("#D4AC0D")
    translate([0, 0, 1.0]) cylinder(d = 19.7, h = 4.2);
}

// Upper electronics puck (circular PCB, 302030 LiPo, O-ring seal, pogo pads)
module electronics_puck() {
    puck_h = 5.6;
    // Lower housing shell + overload hard-stop lip
    color("#1F618D")
    difference() {
        cylinder(d = PUCK_OD, h = puck_h);
        // Cavity for 302030 LiPo + Ø40 mm PCB
        translate([0, 0, 1.2]) cylinder(d = PCB_OD + 2.0, h = puck_h);
    }
    // 302030 150mAh LiPo battery inside pocket
    color("#F39C12")
    translate([-LIPO_L / 2, -LIPO_W / 2, 1.3])
        cube([LIPO_L, LIPO_W, LIPO_H]);
    // Ø40 mm Circular PCB (XIAO nRF52840 / nRF54L15 + NAU7802 + BMA400)
    color("#1E8449")
    translate([0, 0, 4.6])
        cylinder(d = PCB_OD, h = PCB_THICK);
}

// Top waterproof lid + recessed magnetic pogo pads + flush-folding bail
module top_lid_and_bail() {
    color("#2980B9")
    difference() {
        cylinder(d = PUCK_OD, h = TOP_COVER_H);
        // Perimeter recess channel for folding finger bail
        translate([0, 0, 0.8])
            ring(PUCK_OD + 1.0, PUCK_OD - 6.0, TOP_COVER_H);
        // 3-pin recessed magnetic pogo pad pocket
        translate([-6.0, -3.0, TOP_COVER_H - 0.8])
            cube([12.0, 6.0, 1.2]);
    }
    // Gold pogo contacts
    color("#F1C40F")
    for (dx = [-2.54, 0, 2.54]) {
        translate([dx, 0, TOP_COVER_H - 0.6])
            cylinder(d = 1.8, h = 0.7);
    }
    // Flush-folding pivoted finger bail (rotates 90 deg up when lifting bottle)
    color("#D0D3D4")
    translate([0, 0, 0.9])
        difference() {
            ring(PUCK_OD - 0.4, PUCK_OD - 5.2, 1.3);
            translate([-PUCK_OD, -PUCK_OD / 2, -0.5])
                cube([PUCK_OD, PUCK_OD, 2.5]); // Half-arc bail
        }
}

// ----------------------------------------------------------------------------
// Assembly Instantiation
// ----------------------------------------------------------------------------
module full_assembly(z_gap = 0.0) {
    jaw_r = 16.0; // Nominal 32 mm PET cap preview radius

    // 1. Bottom universal 3-jaw scroll clamp
    scroll_collar();
    for (k = [0 : 2]) {
        rotate([0, 0, k * 120]) gripper_jaw(jaw_r);
    }
    translate([0, 0, CHUCK_BASE_H])
        chuck_hub_plate();

    // 2. Sensing stage
    translate([0, 0, CHUCK_BASE_H + 2.0 + z_gap]) {
        if (LOAD_STAGE == "flexure_3spoke") {
            three_spoke_flexure();
        } else {
            fx29_reverse_yoke();
        }
    }

    // 3. Upper electronics puck
    translate([0, 0, CHUCK_BASE_H + 2.0 + FLEXURE_THICK + HARDSTOP_GAP + 2 * z_gap])
        electronics_puck();

    // 4. Top waterproof lid + folding finger bail
    translate([0, 0, CHUCK_BASE_H + 2.0 + FLEXURE_THICK + HARDSTOP_GAP + 5.6 + 3 * z_gap])
        top_lid_and_bail();
}

if (VIEW_MODE == "assembled") {
    full_assembly(0.0);
} else if (VIEW_MODE == "exploded") {
    full_assembly(10.0);
} else {
    // Print plate layout
    scroll_collar();
    translate([PUCK_OD + 8, 0, 0]) chuck_hub_plate();
    translate([-PUCK_OD - 8, 0, 0]) top_lid_and_bail();
    for (k = [0 : 2]) {
        translate([0, PUCK_OD / 2 + 12 + k * 14, 0]) gripper_jaw(0);
    }
}
