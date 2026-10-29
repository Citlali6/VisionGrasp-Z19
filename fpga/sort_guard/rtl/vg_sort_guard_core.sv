// SPDX-License-Identifier: Apache-2.0
// Project-authored candidate gate; not a classifier or an actuator controller.
// All inputs and pulses are synchronous to clk. See ../INTERFACE.md.
module vg_sort_guard_core (
    input wire clk, input wire rst_n, input wire busy,
    input wire arm, input wire cancel, input wire consume, input wire frame_commit,
    input wire [31:0] cfg_job, cfg_baseline, cfg_min_mask, cfg_max_mask, cfg_timeout,
    input wire [15:0] cfg_xmin, cfg_ymin, cfg_xmax, cfg_ymax, cfg_required, cfg_jitter,
    input wire [31:0] frame_seq, frame_mask, frame_job,
    input wire [15:0] frame_xmin, frame_ymin, frame_xmax, frame_ymax,
    input wire frame_valid, frame_fresh,
    output wire arm_allowed, output wire frame_allowed, output wire consume_allowed,
    output reg active, output reg ready, output reg consumed,
    output reg timed_out, output reg cancelled, output reg permit_pulse,
    output reg [31:0] active_job, last_seq, age_cycles, permit_count, permit_job,
    output reg [15:0] stable_count,
    output reg [3:0] last_reason
);
    reg [31:0] min_mask, max_mask, timeout_cycles;
    reg [15:0] xmin, ymin, xmax, ymax, required_frames, jitter;
    reg [15:0] anchor_xmin, anchor_ymin, anchor_xmax, anchor_ymax;
    reg anchor_valid;
    wire cfg_valid = cfg_job != 0 && cfg_xmin <= cfg_xmax && cfg_ymin <= cfg_ymax
        && cfg_min_mask != 0 && cfg_min_mask <= cfg_max_mask
        && cfg_required != 0 && cfg_timeout != 0;
    wire expired = active && age_cycles >= timeout_cycles - 32'd1;
    assign arm_allowed = !active && !busy && cfg_valid;
    assign frame_allowed = active && !busy && !expired && frame_job == active_job;
    assign consume_allowed = active && ready && !busy && !expired;
    wire [31:0] seq_delta = frame_seq - last_seq;
    wire newer = seq_delta != 0 && !seq_delta[31];
    wire frame_ok = frame_valid && frame_fresh
        && frame_xmin <= frame_xmax && frame_ymin <= frame_ymax
        && frame_xmin >= xmin && frame_xmax <= xmax
        && frame_ymin >= ymin && frame_ymax <= ymax
        && frame_mask >= min_mask && frame_mask <= max_mask;
    function automatic [15:0] distance16;
        input [15:0] a, b;
        begin distance16 = (a >= b) ? a-b : b-a; end
    endfunction
    wire position_ok = distance16(frame_xmin, anchor_xmin) <= jitter
        && distance16(frame_ymin, anchor_ymin) <= jitter
        && distance16(frame_xmax, anchor_xmax) <= jitter
        && distance16(frame_ymax, anchor_ymax) <= jitter;

    always @(posedge clk) begin
        if (!rst_n) begin
            active<=0; ready<=0; consumed<=0; timed_out<=0; cancelled<=0;
            permit_pulse<=0; active_job<=0; last_seq<=0; age_cycles<=0;
            permit_count<=0; permit_job<=0; stable_count<=0; last_reason<=0;
            min_mask<=0; max_mask<=0; timeout_cycles<=0;
            xmin<=0; ymin<=0; xmax<=0; ymax<=0; required_frames<=0; jitter<=0;
            anchor_xmin<=0; anchor_ymin<=0; anchor_xmax<=0; anchor_ymax<=0;
            anchor_valid<=0;
        end else begin
            permit_pulse <= 0;
            if (busy) begin
                if (active || cancel) begin
                    active<=0; ready<=0; stable_count<=0; anchor_valid<=0;
                    cancelled<=1; last_reason<=8;
                end
            end else if (cancel) begin
                active<=0; ready<=0; stable_count<=0; anchor_valid<=0;
                cancelled<=1; last_reason<=7;
            end else if (expired) begin
                active<=0; ready<=0; stable_count<=0; anchor_valid<=0;
                timed_out<=1; last_reason<=6; age_cycles<=timeout_cycles;
            end else begin
                if (active) age_cycles <= age_cycles + 32'd1;
                if (arm && arm_allowed) begin
                    active<=1; ready<=0; consumed<=0; timed_out<=0; cancelled<=0;
                    active_job<=cfg_job; last_seq<=cfg_baseline;
                    age_cycles<=0; stable_count<=0; anchor_valid<=0; last_reason<=1;
                    min_mask<=cfg_min_mask; max_mask<=cfg_max_mask; timeout_cycles<=cfg_timeout;
                    xmin<=cfg_xmin; ymin<=cfg_ymin; xmax<=cfg_xmax; ymax<=cfg_ymax;
                    required_frames<=cfg_required; jitter<=cfg_jitter;
                end else if (frame_commit && frame_allowed) begin
                    if (newer) begin
                        last_seq <= frame_seq;
                        if (frame_valid && frame_fresh) age_cycles <= 0;
                        if (!frame_ok) begin
                            ready<=0; stable_count<=0; anchor_valid<=0; last_reason<=4;
                        end else if (!anchor_valid) begin
                            anchor_xmin<=frame_xmin; anchor_ymin<=frame_ymin;
                            anchor_xmax<=frame_xmax; anchor_ymax<=frame_ymax;
                            anchor_valid<=1; stable_count<=1;
                            ready <= required_frames == 1;
                            last_reason <= (required_frames == 1) ? 3 : 2;
                        end else if (!position_ok) begin
                            ready<=0; stable_count<=0; anchor_valid<=0; last_reason<=5;
                        end else begin
                            if (stable_count < required_frames) stable_count <= stable_count + 16'd1;
                            if (stable_count >= required_frames - 16'd1) begin
                                ready<=1; last_reason<=3;
                            end else last_reason<=2;
                        end
                    end
                end else if (consume && consume_allowed) begin
                    active<=0; ready<=0; stable_count<=0; anchor_valid<=0;
                    consumed<=1; permit_pulse<=1;
                    permit_count<=permit_count+32'd1; permit_job<=active_job; last_reason<=9;
                end
            end
        end
    end
endmodule
