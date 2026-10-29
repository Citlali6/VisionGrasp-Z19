// SPDX-License-Identifier: Apache-2.0
// Project-authored AXI4-Lite endpoint. Independent AW/W holding registers follow
// the repository's vg_color_axi pattern; this endpoint reports SLVERR and has no
// dependency on the old color bitstream, address map or actuator outputs.
module vg_sort_guard_axi (
    input wire clk, input wire rst_n, input wire external_busy,
    input wire [11:0] s_axi_awaddr,
    input wire s_axi_awvalid, output wire s_axi_awready,
    input wire [31:0] s_axi_wdata, input wire [3:0] s_axi_wstrb,
    input wire s_axi_wvalid, output wire s_axi_wready,
    output wire [1:0] s_axi_bresp, output wire s_axi_bvalid, input wire s_axi_bready,
    input wire [11:0] s_axi_araddr,
    input wire s_axi_arvalid, output wire s_axi_arready,
    output wire [31:0] s_axi_rdata, output wire [1:0] s_axi_rresp,
    output wire s_axi_rvalid, input wire s_axi_rready,
    output wire permit_pulse
);
    reg aw_hold, w_hold, b_valid, r_valid;
    reg [11:0] aw_address;
    reg [31:0] w_data, r_data;
    reg [3:0] w_strb;
    reg [1:0] b_resp, r_resp;
    reg software_busy, bus_fault;
    reg [31:0] cfg_job, cfg_baseline, cfg_min_mask, cfg_max_mask, cfg_timeout;
    reg [15:0] cfg_xmin, cfg_ymin, cfg_xmax, cfg_ymax, cfg_required, cfg_jitter;
    reg [31:0] frame_seq, frame_mask, frame_job;
    reg [15:0] frame_xmin, frame_ymin, frame_xmax, frame_ymax;
    reg [1:0] frame_flags;
    wire write_fire = aw_hold && w_hold && !b_valid;
    wire full_write = w_strb == 4'hf && aw_address[1:0] == 0;
    // A BUSY=1 write revokes the core on the same commit edge as the AXI write.
    wire busy = software_busy || external_busy
        || (write_fire && full_write && aw_address==12'h00c && w_data==1);
    wire arm_allowed, frame_allowed, consume_allowed;
    wire active, ready, consumed, timed_out, cancelled;
    wire [31:0] active_job, last_seq, age_cycles, permit_count, permit_job;
    wire [15:0] stable_count;
    wire [3:0] last_reason;
    wire command_write = write_fire && full_write && aw_address == 12'h008;
    vg_sort_guard_core core (
        .clk(clk), .rst_n(rst_n), .busy(busy),
        .arm(command_write && w_data==1 && arm_allowed),
        .cancel(command_write && w_data==2),
        .consume(command_write && w_data==4 && consume_allowed),
        .frame_commit(command_write && w_data==8 && frame_allowed),
        .cfg_job(cfg_job), .cfg_baseline(cfg_baseline),
        .cfg_min_mask(cfg_min_mask), .cfg_max_mask(cfg_max_mask), .cfg_timeout(cfg_timeout),
        .cfg_xmin(cfg_xmin), .cfg_ymin(cfg_ymin), .cfg_xmax(cfg_xmax), .cfg_ymax(cfg_ymax),
        .cfg_required(cfg_required), .cfg_jitter(cfg_jitter),
        .frame_seq(frame_seq), .frame_mask(frame_mask), .frame_job(frame_job),
        .frame_xmin(frame_xmin), .frame_ymin(frame_ymin), .frame_xmax(frame_xmax), .frame_ymax(frame_ymax),
        .frame_valid(frame_flags[0]), .frame_fresh(frame_flags[1]),
        .arm_allowed(arm_allowed), .frame_allowed(frame_allowed), .consume_allowed(consume_allowed),
        .active(active), .ready(ready), .consumed(consumed), .timed_out(timed_out),
        .cancelled(cancelled), .permit_pulse(permit_pulse),
        .active_job(active_job), .last_seq(last_seq), .age_cycles(age_cycles),
        .permit_count(permit_count), .permit_job(permit_job),
        .stable_count(stable_count), .last_reason(last_reason)
    );
    assign s_axi_awready = !aw_hold && !b_valid;
    assign s_axi_wready = !w_hold && !b_valid;
    assign s_axi_bvalid = b_valid;
    assign s_axi_bresp = b_resp;
    assign s_axi_arready = !r_valid;
    assign s_axi_rvalid = r_valid;
    assign s_axi_rdata = r_data;
    assign s_axi_rresp = r_resp;

    reg write_ok;
    always @* begin
        write_ok = full_write;
        if (full_write) begin
            case (aw_address)
                12'h008: case (w_data)
                    1: write_ok=arm_allowed;
                    2,16: write_ok=1;
                    4: write_ok=consume_allowed;
                    8: write_ok=frame_allowed;
                    default: write_ok=0;
                endcase
                12'h00c: write_ok=w_data<=1;
                12'h040,12'h044,12'h058,12'h05c,12'h068,
                12'h080,12'h084,12'h09c: write_ok=1;
                12'h048,12'h04c,12'h050,12'h054,12'h060,12'h064,
                12'h088,12'h08c,12'h090,12'h094: write_ok=w_data[31:16]==0;
                12'h098: write_ok=w_data[31:2]==0;
                default: write_ok=0;
            endcase
        end
    end
    reg [31:0] read_value;
    reg read_ok;
    always @* begin
        read_ok=1; read_value=0;
        case (s_axi_araddr)
            12'h000: read_value=32'h31444753;
            12'h004: read_value=32'h00010000;
            12'h008: read_value=0;
            12'h00c: read_value={31'b0,software_busy};
            12'h010: read_value={25'b0,bus_fault,cancelled,timed_out,consumed,busy,ready,active};
            12'h014: read_value=active_job;
            12'h018: read_value=last_seq;
            12'h01c: read_value={16'b0,stable_count};
            12'h020: read_value=age_cycles;
            12'h024: read_value=permit_count;
            12'h028: read_value=permit_job;
            12'h02c: read_value={28'b0,last_reason};
            12'h040: read_value=cfg_job;
            12'h044: read_value=cfg_baseline;
            12'h048: read_value={16'b0,cfg_xmin};
            12'h04c: read_value={16'b0,cfg_ymin};
            12'h050: read_value={16'b0,cfg_xmax};
            12'h054: read_value={16'b0,cfg_ymax};
            12'h058: read_value=cfg_min_mask;
            12'h05c: read_value=cfg_max_mask;
            12'h060: read_value={16'b0,cfg_required};
            12'h064: read_value={16'b0,cfg_jitter};
            12'h068: read_value=cfg_timeout;
            12'h080: read_value=frame_seq;
            12'h084: read_value=frame_mask;
            12'h088: read_value={16'b0,frame_xmin};
            12'h08c: read_value={16'b0,frame_ymin};
            12'h090: read_value={16'b0,frame_xmax};
            12'h094: read_value={16'b0,frame_ymax};
            12'h098: read_value={30'b0,frame_flags};
            12'h09c: read_value=frame_job;
            default: read_ok=0;
        endcase
    end
    always @(posedge clk) begin
        if (!rst_n) begin
            aw_hold<=0; w_hold<=0; b_valid<=0; r_valid<=0;
            aw_address<=0; w_data<=0; w_strb<=0; b_resp<=0; r_resp<=0; r_data<=0;
            software_busy<=0; bus_fault<=0;
            cfg_job<=0; cfg_baseline<=0; cfg_min_mask<=0; cfg_max_mask<=0; cfg_timeout<=0;
            cfg_xmin<=0; cfg_ymin<=0; cfg_xmax<=0; cfg_ymax<=0; cfg_required<=0; cfg_jitter<=0;
            frame_seq<=0; frame_mask<=0; frame_job<=0;
            frame_xmin<=0; frame_ymin<=0; frame_xmax<=0; frame_ymax<=0; frame_flags<=0;
        end else begin
            if (b_valid && s_axi_bready) b_valid<=0;
            if (r_valid && s_axi_rready) r_valid<=0;
            if (s_axi_awvalid && s_axi_awready) begin aw_hold<=1; aw_address<=s_axi_awaddr; end
            if (s_axi_wvalid && s_axi_wready) begin w_hold<=1; w_data<=s_axi_wdata; w_strb<=s_axi_wstrb; end
            if (write_fire) begin
                aw_hold<=0; w_hold<=0; b_valid<=1;
                b_resp <= write_ok ? 2'b00 : 2'b10;
                if (!write_ok) bus_fault<=1;
                else case (aw_address)
                    12'h008: if (w_data==16) bus_fault<=0;
                    12'h00c: software_busy<=w_data[0];
                    12'h040: cfg_job<=w_data;
                    12'h044: cfg_baseline<=w_data;
                    12'h048: cfg_xmin<=w_data[15:0];
                    12'h04c: cfg_ymin<=w_data[15:0];
                    12'h050: cfg_xmax<=w_data[15:0];
                    12'h054: cfg_ymax<=w_data[15:0];
                    12'h058: cfg_min_mask<=w_data;
                    12'h05c: cfg_max_mask<=w_data;
                    12'h060: cfg_required<=w_data[15:0];
                    12'h064: cfg_jitter<=w_data[15:0];
                    12'h068: cfg_timeout<=w_data;
                    12'h080: frame_seq<=w_data;
                    12'h084: frame_mask<=w_data;
                    12'h088: frame_xmin<=w_data[15:0];
                    12'h08c: frame_ymin<=w_data[15:0];
                    12'h090: frame_xmax<=w_data[15:0];
                    12'h094: frame_ymax<=w_data[15:0];
                    12'h098: frame_flags<=w_data[1:0];
                    12'h09c: frame_job<=w_data;
                    default: ;
                endcase
            end
            if (s_axi_arvalid && s_axi_arready) begin
                r_valid<=1; r_data<=read_value; r_resp<=read_ok ? 2'b00 : 2'b10;
                if (!read_ok) bus_fault<=1;
            end
        end
    end
endmodule
