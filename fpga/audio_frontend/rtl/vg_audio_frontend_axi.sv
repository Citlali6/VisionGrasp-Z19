// SPDX-License-Identifier: Apache-2.0
// PIO PCM16 frontend. ABI source: fpga/system_pspl/registers.json.
// Single clock; sample timing is represented by ready/valid, not a new clock.
module vg_audio_frontend_axi (
    input wire clk, input wire rst_n,
    input wire [11:0] s_axi_awaddr, input wire s_axi_awvalid, output wire s_axi_awready,
    input wire [31:0] s_axi_wdata, input wire [3:0] s_axi_wstrb,
    input wire s_axi_wvalid, output wire s_axi_wready,
    output wire [1:0] s_axi_bresp, output wire s_axi_bvalid, input wire s_axi_bready,
    input wire [11:0] s_axi_araddr, input wire s_axi_arvalid, output wire s_axi_arready,
    output wire [31:0] s_axi_rdata, output wire [1:0] s_axi_rresp,
    output wire s_axi_rvalid, input wire s_axi_rready
);
    `include "registers.svh"
    wire wr_valid, rd_valid;
    wire [11:0] wr_addr, rd_addr;
    wire [31:0] wr_data;
    wire [3:0] wr_strb;
    reg wr_error, rd_error;
    reg [31:0] rd_data;
    vg_axil_regs bus (
        .clk(clk),.rst_n(rst_n),
        .s_axi_awaddr(s_axi_awaddr),.s_axi_awvalid(s_axi_awvalid),.s_axi_awready(s_axi_awready),
        .s_axi_wdata(s_axi_wdata),.s_axi_wstrb(s_axi_wstrb),.s_axi_wvalid(s_axi_wvalid),.s_axi_wready(s_axi_wready),
        .s_axi_bresp(s_axi_bresp),.s_axi_bvalid(s_axi_bvalid),.s_axi_bready(s_axi_bready),
        .s_axi_araddr(s_axi_araddr),.s_axi_arvalid(s_axi_arvalid),.s_axi_arready(s_axi_arready),
        .s_axi_rdata(s_axi_rdata),.s_axi_rresp(s_axi_rresp),.s_axi_rvalid(s_axi_rvalid),.s_axi_rready(s_axi_rready),
        .wr_valid(wr_valid),.wr_addr(wr_addr),.wr_data(wr_data),.wr_strb(wr_strb),.wr_error(wr_error),
        .rd_valid(rd_valid),.rd_addr(rd_addr),.rd_data(rd_data),.rd_error(rd_error)
    );
    reg enabled, bypass, config_valid, soft_reset, config_reset;
    reg [31:0] errors, input_count, output_count, produced_count, clip_count, config_version;
    reg [5:0] coefficient_index;
    reg signed [15:0] staged_coefficients [0:62];
    reg [62:0] loaded;
    reg [1007:0] coefficients;
    reg [31:0] st_open, st_close, st_attack, st_release, st_flags, st_id;
    reg [15:0] open_threshold, close_threshold, attack_step, release_step;
    reg [2:0] flags;
    wire pipeline_resetn = rst_n && !soft_reset && !config_reset;
    wire input_ready, input_valid, input_pop, output_valid, output_pop;
    wire signed [15:0] input_data, output_data, dc_data, fir_data, gate_data;
    wire dc_valid, dc_ready, fir_valid, fir_ready, gate_valid, gate_ready, fir_busy;
    wire clip_dc, clip_fir, clip_gate;
    wire [4:0] input_fill, output_fill;
    wire busy = input_fill != 0 || output_fill != 0 || dc_valid || fir_busy || gate_valid;
    reg staged_nonzero;
    reg [6:0] loaded_count;
    integer j;
    always @* begin
        staged_nonzero = 0; loaded_count = 0;
        for (j=0;j<63;j=j+1) begin
            staged_nonzero = staged_nonzero || staged_coefficients[j] != 0;
            loaded_count = loaded_count + {6'b0,loaded[j]};
        end
    end
    wire staging_valid = &loaded && staged_nonzero && st_open > st_close && st_open <= 32768 &&
                         st_attack >= 1 && st_attack <= 32768 && st_release >= 1 && st_release <= 32768 &&
                         st_flags <= 7;
    wire write_fire = wr_valid && !wr_error && wr_strb == 4'hf;
    wire push_input = write_fire && wr_addr == PSPL_R_INPUT;
    assign output_pop = rd_valid && !rd_error && rd_addr == PSPL_R_OUTPUT;
    vg_sync_fifo #(.WIDTH(16),.DEPTH(16)) input_fifo (
        .clk(clk),.rst_n(pipeline_resetn),.s_data(wr_data[15:0]),.s_valid(push_input),.s_ready(input_ready),
        .m_data(input_data),.m_valid(input_valid),.m_ready(input_pop),.count(input_fill)
    );
    vg_audio_dc_axis dc (
        .clk(clk),.resetn(pipeline_resetn),.bypass(bypass || !flags[0]),
        .s_data(input_data),.s_valid(input_valid),.s_ready(input_pop),
        .m_data(dc_data),.m_valid(dc_valid),.m_ready(dc_ready),.clipped(clip_dc)
    );
    vg_audio_fir_axis fir (
        .clk(clk),.resetn(pipeline_resetn),.bypass(bypass || !flags[1]),.coefficients(coefficients),
        .s_data(dc_data),.s_valid(dc_valid),.s_ready(dc_ready),
        .m_data(fir_data),.m_valid(fir_valid),.m_ready(fir_ready),.busy(fir_busy),.clipped(clip_fir)
    );
    vg_audio_gate_axis gate (
        .clk(clk),.resetn(pipeline_resetn),.bypass(bypass || !flags[2]),
        .open_threshold(open_threshold),.close_threshold(close_threshold),
        .attack_step(attack_step),.release_step(release_step),
        .s_data(fir_data),.s_valid(fir_valid),.s_ready(fir_ready),
        .m_data(gate_data),.m_valid(gate_valid),.m_ready(gate_ready),.clipped(clip_gate)
    );
    vg_sync_fifo #(.WIDTH(16),.DEPTH(16)) output_fifo (
        .clk(clk),.rst_n(pipeline_resetn),.s_data(gate_data),.s_valid(gate_valid),.s_ready(gate_ready),
        .m_data(output_data),.m_valid(output_valid),.m_ready(output_pop),.count(output_fill)
    );
    // Atomic commands/data require full WSTRB. Zero WSTRB is a no-op; partial
    // writes return SLVERR without side effects. PS uses aligned uint32 MMIO.
    always @* begin
        wr_error = 0;
        if (wr_strb != 0) begin
            if (wr_strb != 4'hf) wr_error = 1;
            else case (wr_addr)
                PSPL_R_CONTROL: begin
                    if (wr_data & 32'hffffffe0) wr_error = 1;
                    else if (!wr_data[2]) begin
                        if (wr_data[3] && (enabled || busy || !staging_valid)) wr_error = 1;
                        if (wr_data[1] != bypass && (enabled || busy)) wr_error = 1;
                        if (wr_data[0] && (!config_valid || wr_data[3] || soft_reset || config_reset)) wr_error = 1;
                    end
                end
                PSPL_R_ERROR: ;
                PSPL_R_INPUT: if (!enabled || !config_valid || !input_ready || !pipeline_resetn || wr_data[31:16] != 0) wr_error = 1;
                PSPL_A_COEFF_INDEX: if (enabled || busy || wr_data > 62) wr_error = 1;
                PSPL_A_COEFF_VALUE: if (enabled || busy || coefficient_index > 62 ||
                              (wr_data[31:16] != 0 && wr_data[31:16] != {16{wr_data[15]}})) wr_error = 1;
                PSPL_A_GATE_OPEN,PSPL_A_GATE_CLOSE,PSPL_A_ATTACK,PSPL_A_RELEASE,PSPL_A_FLAGS,PSPL_A_CONFIG_ID: if (enabled || busy) wr_error = 1;
                default: wr_error = 1;
            endcase
        end
    end
    always @* begin
        rd_data = 0; rd_error = 0;
        case (rd_addr)
            PSPL_R_ID: rd_data = 32'h56474132;
            PSPL_R_VERSION: rd_data = 1;
            PSPL_R_CAPABILITIES: rd_data = 32'h00000007;
            PSPL_R_CONTROL: rd_data = {30'b0,bypass,enabled};
            PSPL_R_STATUS: rd_data = {27'b0,1'b0,config_valid,busy,output_valid,(input_ready && enabled && config_valid && pipeline_resetn)};
            PSPL_R_ERROR: rd_data = errors;
            PSPL_R_IN_COUNT: rd_data = input_count;
            PSPL_R_OUT_COUNT: rd_data = output_count;
            PSPL_R_OUTPUT: begin rd_data = output_valid ? {16'b0,output_data} : 32'b0; if (!output_valid) rd_error = 1; end
            PSPL_R_CONFIG_VERSION: rd_data = config_version;
            PSPL_R_COMPLETE: rd_data = produced_count;
            PSPL_A_COEFF_INDEX: rd_data = {26'b0,coefficient_index};
            PSPL_A_COEFF_VALUE: rd_data = {{16{staged_coefficients[coefficient_index][15]}},staged_coefficients[coefficient_index]};
            PSPL_A_GATE_OPEN: rd_data = st_open;
            PSPL_A_GATE_CLOSE: rd_data = st_close;
            PSPL_A_ATTACK: rd_data = st_attack;
            PSPL_A_RELEASE: rd_data = st_release;
            PSPL_A_FLAGS: rd_data = st_flags;
            PSPL_A_CONFIG_ID: rd_data = st_id;
            PSPL_A_COEFF_LOADED: rd_data = {25'b0,loaded_count};
            PSPL_A_CLIP_COUNT: rd_data = clip_count;
            PSPL_A_OCCUPANCY: rd_data = {11'b0,output_fill,11'b0,input_fill};
            default: rd_error = 1;
        endcase
    end
    wire [2:0] clips_this_cycle = {2'b0,clip_dc} + {2'b0,clip_fir} + {2'b0,clip_gate};
    wire [32:0] clips_sum = {1'b0,clip_count} + {30'b0,clips_this_cycle};
    wire [31:0] error_set = (wr_valid && wr_error ? 32'd1 : 32'd0) |
                           (rd_valid && rd_error ? 32'd2 : 32'd0) |
                           (wr_valid && wr_error && wr_addr == PSPL_R_INPUT && !input_ready ? 32'd4 : 32'd0) |
                           (rd_valid && rd_error && rd_addr == PSPL_R_OUTPUT && !output_valid ? 32'd8 : 32'd0) |
                           (wr_valid && wr_error && wr_addr == PSPL_R_CONTROL ? 32'd16 : 32'd0);
    wire clear_errors = write_fire && wr_addr == PSPL_R_ERROR;
    integer i;
    always @(posedge clk) begin
        if (!rst_n) begin
            enabled <= 0; bypass <= 0; config_valid <= 0; soft_reset <= 0; config_reset <= 0;
            errors <= 0; input_count <= 0; output_count <= 0; produced_count <= 0; clip_count <= 0;
            config_version <= 0; coefficient_index <= 0; loaded <= 0; coefficients <= 0;
            st_open <= 400; st_close <= 200; st_attack <= 1024; st_release <= 64; st_flags <= 3; st_id <= 0;
            open_threshold <= 400; close_threshold <= 200; attack_step <= 1024; release_step <= 64; flags <= 0;
            for (i=0;i<63;i=i+1) staged_coefficients[i] <= 0;
        end else begin
            soft_reset <= 0; config_reset <= 0;
            if (pipeline_resetn) begin
                if (clips_this_cycle != 0) clip_count <= clips_sum[32] ? 32'hffffffff : clips_sum[31:0];
                if (gate_valid && gate_ready) produced_count <= produced_count + 1'b1;
                if (push_input) input_count <= input_count + 1'b1;
                if (output_pop) output_count <= output_count + 1'b1;
            end
            // Hardware errors are sticky; a new error dominates simultaneous W1C.
            if (clear_errors || error_set != 0)
                errors <= (errors & ~(clear_errors ? wr_data : 32'b0)) | error_set;
            if (write_fire) case (wr_addr)
                PSPL_R_CONTROL: begin
                    if (wr_data[2]) begin
                        soft_reset <= 1; enabled <= 0; bypass <= 0; config_valid <= 0;
                        loaded <= 0; config_version <= 0; errors <= 0;
                        input_count <= 0; output_count <= 0; produced_count <= 0; clip_count <= 0;
                    end else begin
                        enabled <= wr_data[0]; bypass <= wr_data[1];
                        if (wr_data[3]) begin
                            for (i=0;i<63;i=i+1) coefficients[16*i +: 16] <= staged_coefficients[i];
                            open_threshold <= st_open[15:0]; close_threshold <= st_close[15:0];
                            attack_step <= st_attack[15:0]; release_step <= st_release[15:0]; flags <= st_flags[2:0];
                            config_version <= st_id; config_valid <= 1; config_reset <= 1;
                        end
                    end
                end
                PSPL_A_COEFF_INDEX: coefficient_index <= wr_data[5:0];
                PSPL_A_COEFF_VALUE: begin staged_coefficients[coefficient_index] <= wr_data[15:0]; loaded[coefficient_index] <= 1; end
                PSPL_A_GATE_OPEN: st_open <= wr_data;
                PSPL_A_GATE_CLOSE: st_close <= wr_data;
                PSPL_A_ATTACK: st_attack <= wr_data;
                PSPL_A_RELEASE: st_release <= wr_data;
                PSPL_A_FLAGS: st_flags <= wr_data;
                PSPL_A_CONFIG_ID: st_id <= wr_data;
                default: ;
            endcase
        end
    end
endmodule
