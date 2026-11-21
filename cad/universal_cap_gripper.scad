// ============================================================================
// HydroCap: 1.1x D_cap Proportioned Waterproof Universal Bottle-Cap CAD
// Parametric OpenSCAD Design:
//   - Universal Ø28.0 mm PCBWay Core + Ø30.0 mm 301-SS 3-Spoke Flexure
//   - Outer Diameter = 1.10 x D_cap across 4 bottle tiers:
//       "pet_30"   : 30.5 mm cap -> 33.6 mm HydroCap (zero overhang!)
//       "sport_40" : 41.0 mm cap -> 45.1 mm HydroCap
//       "flask_48" : 48.0 mm cap -> 52.8 mm HydroCap
//       "wide_63"  : 63.0 mm cap -> 69.3 mm HydroCap
// ============================================================================

CAP_TIER    = "pet_30";         // "pet_30" | "sport_40" | "flask_48" | "wide_63"
LOAD_STAGE  = "flexure_3spoke"; // "flexure_3spoke" (0.8 mm SS) | "fx29_yoke"
VIEW_MODE   = "assembled";      // "assembled" | "exploded" | "print_plate"

CAP_OD_NOM = (CAP_TIER == "pet_30")   ? 30.5 :
             (CAP_TIER == "sport_40") ? 41.0 :
             (CAP_TIER == "flask_48") ? 48.0 : 63.0;

// Exact 1.10x proportional diameter rule
PUCK_OD    = CAP_OD_NOM * 1.10;         // 33.55 -> 33.6 mm for pet_30

CHUCK_BASE_H  = 5.2;
FLEXURE_OD    = 30.0;                   // Universal Ø30 mm core fits all 4 shells
FLEXURE_THICK = (LOAD_STAGE == "flexure_3spoke") ? 0.8 : 5.2;
HARDSTOP_GAP  = 0.35;
PCB_OD        = 28.0;                   // Universal Ø28.0 mm PCBWay V2.1 core
PCB_THICK     = 0.8;
LIPO_L        = 20.0;                   // 401520 100 mAh LiPo (diagonal 25.0 mm)
LIPO_W        = 15.0;
LIPO_H        = 4.0;
TOP_COVER_H   = 2.0;

$fn = 72;

module ring(od, id, h) {
    difference() {
        cylinder(d = od, h = h);
        translate([0, 0, -0.5]) cylinder(d = id, h = h + 1.0);
    }
}

// Tapered compression sleeve (1.10x D_cap OD)
module compression_collar() {
    color("#34495E")
    difference() {
        union() {
            ring(PUCK_OD, CAP_OD_NOM + 0.6, CHUCK_BASE_H);
            for (i = [0 : 35]) {
                rotate([0, 0, i * 10])
                    translate([PUCK_OD / 2 - 0.25, -0.6, 0.4])
                        cube([0.55, 1.2, CHUCK_BASE_H - 0.8]);
            }
        }
    }
}

// 6-petal compliant TPU 85A / Shore 50A grip collet (flexes +/- 1.8 mm)
module split_grip_collet() {
    color("#E67E22")
    for (k = [0 : 5]) {
        rotate([0, 0, k * 60])
            translate([CAP_OD_NOM / 2 - 0.6, -5.0, 0.5])
                cube([1.3, 10.0, CHUCK_BASE_H - 0.8]);
    }
}

// Inner flexure carrier hub + RTV wire gland
module chuck_hub_plate() {
    color("#5D6D7E")
    difference() {
        cylinder(d = min(PUCK_OD - 1.2, FLEXURE_OD + 2.0), h = 1.8);
        translate([0, 0, -0.5]) cylinder(d = 3.6, h = 2.8);
    }
}

// Universal Ø30.0 mm x 0.8 mm 301-SS 3-spoke moment-cancelling flexure
module three_spoke_flexure() {
    outer_od = FLEXURE_OD;
    outer_id = 24.0;
    hub_od   = 11.0;
    spoke_w  = 4.2;
    color("#BDC3C7")
    union() {
        ring(outer_od, outer_id, 0.8);
        cylinder(d = hub_od, h = 0.8);
        for (k = [0 : 2]) {
            rotate([0, 0, k * 120])
                translate([hub_od / 2 - 1.0, -spoke_w / 2, 0])
                    cube([(outer_id - hub_od) / 2 + 2.0, spoke_w, 0.8]);
        }
    }
}

// Upper electronics puck (Ø28 mm PCB + 401520 LiPo + O-ring + IPX8 USB-C)
module electronics_puck() {
    puck_h = 5.6;
    color("#1F618D")
    difference() {
        cylinder(d = PUCK_OD, h = puck_h);
        translate([0, 0, 1.0]) cylinder(d = PCB_OD + 1.2, h = puck_h);
        // Side IPX8 USB-C cutout at -Y perimeter
        translate([-4.7, -PUCK_OD / 2 - 1.0, 1.8]) cube([9.4, 12.0, 3.8]);
    }
    // 401520 100 mAh LiPo pouch (20 x 15 x 4.0 mm)
    color("#F39C12")
    translate([-LIPO_L / 2, -LIPO_W / 2, 1.1]) cube([LIPO_L, LIPO_W, LIPO_H]);
    // Ø28.0 mm Circular V2.1 PCBWay PCB
    color("#0B5345")
    translate([0, 0, 5.1]) cylinder(d = PCB_OD, h = PCB_THICK);
}

module usbc_tpu_plug() {
    color("#E74C3C")
    translate([-4.5, -PUCK_OD / 2 - 1.0, 1.9]) {
        cube([9.0, 2.4, 3.4]);
        translate([1.3, 2.0, 0.4]) cube([6.4, 3.5, 2.4]);
    }
}

module top_lid_and_bail() {
    color("#2980B9")
    difference() {
        cylinder(d = PUCK_OD, h = TOP_COVER_H);
        translate([0, 0, 0.7]) ring(PUCK_OD + 1.0, PUCK_OD - 4.4, TOP_COVER_H);
    }
    color("#D0D3D4")
    translate([0, 0, 0.8])
        difference() {
            ring(PUCK_OD - 0.3, PUCK_OD - 4.0, 1.2);
            translate([-PUCK_OD, -PUCK_OD / 2, -0.5]) cube([PUCK_OD, PUCK_OD, 2.5]);
        }
}

module full_assembly(z_gap = 0.0) {
    compression_collar();
    split_grip_collet();
    translate([0, 0, CHUCK_BASE_H]) chuck_hub_plate();
    translate([0, 0, CHUCK_BASE_H + 1.8 + z_gap]) three_spoke_flexure();
    z_puck = CHUCK_BASE_H + 1.8 + FLEXURE_THICK + HARDSTOP_GAP + 2 * z_gap;
    translate([0, 0, z_puck]) {
        electronics_puck();
        usbc_tpu_plug();
    }
    translate([0, 0, z_puck + 5.6 + z_gap]) top_lid_and_bail();
}

if (VIEW_MODE == "assembled") full_assembly(0.0);
else if (VIEW_MODE == "exploded") full_assembly(8.0);
else {
    compression_collar();
    translate([PUCK_OD + 6, 0, 0]) chuck_hub_plate();
    translate([-PUCK_OD - 6, 0, 0]) top_lid_and_bail();
    translate([0, -PUCK_OD / 2 - 12, 0]) usbc_tpu_plug();
}
