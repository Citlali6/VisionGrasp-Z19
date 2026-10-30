// SPDX-License-Identifier: Apache-2.0
// Source profile VGV2. Register contract: system_pspl/registers.json.
// One frame in flight. The first accepted PIO SOF freezes the COMPLETE pending
// configuration until the snapshot is acknowledged. Therefore all downstream
// stages see exactly that configuration even if PS commits the next one early.
module vg_video_axi (
    input wire clk,input wire rst_n,
    input wire [11:0] s_axi_awaddr,input wire s_axi_awvalid,output wire s_axi_awready,
    input wire [31:0] s_axi_wdata,input wire [3:0] s_axi_wstrb,
    input wire s_axi_wvalid,output wire s_axi_wready,
    output wire [1:0] s_axi_bresp,output wire s_axi_bvalid,input wire s_axi_bready,
    input wire [11:0] s_axi_araddr,input wire s_axi_arvalid,output wire s_axi_arready,
    output wire [31:0] s_axi_rdata,output wire [1:0] s_axi_rresp,
    output wire s_axi_rvalid,input wire s_axi_rready
);
    `include "registers.svh"
    wire wr_valid,rd_valid;
    wire [11:0] wr_addr,rd_addr;
    wire [31:0] wr_data;
    wire [3:0] wr_strb;
    reg wr_error,rd_error;
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
    // stage[0..14]: dimensions, gains, signed biases, HSV min/max, ROI, version.
    reg [31:0] stage[0:14],pending[0:14],active[0:14];
    reg pending_valid,pending_bypass,active_bypass;
    reg enable,bypass_control,soft_reset,frame_busy,snapshot_valid,frame_error;
    reg [31:0] errors,input_count,output_count,completed,snapshot_frame,clip_count;
    reg [31:0] frame_inputs;
    reg [15:0] in_x,in_y;
    wire pipe_resetn=rst_n && !soft_reset;
    wire [31:0] active_total=active[0]*active[1];
    wire [31:0] first_total=pending[0]*pending[1];
    wire [31:0] frame_total=frame_busy ? active_total : first_total;
    reg stage_ok;
    always @* begin
        stage_ok=stage[0]>=1 && stage[0]<=4096 && stage[1]>=1 && stage[1]<=4096 &&
            stage[2]<=1024 && stage[3]<=1024 && stage[4]<=1024 &&
            $signed(stage[5])>=-32'sd255 && $signed(stage[5])<=32'sd255 &&
            $signed(stage[6])>=-32'sd255 && $signed(stage[6])<=32'sd255 &&
            $signed(stage[7])>=-32'sd255 && $signed(stage[7])<=32'sd255 &&
            stage[8][31:24]==0 && stage[9][31:24]==0 &&
            stage[8][7:0]<=179 && stage[9][7:0]<=179 &&
            stage[8][15:8]<=stage[9][15:8] && stage[8][23:16]<=stage[9][23:16] &&
            stage[10]<=stage[12] && stage[11]<=stage[13] &&
            stage[12]<stage[0] && stage[13]<stage[1];
    end
    wire in_ready,in_valid,in_take;
    wire [31:0] in_word;
    wire [4:0] in_fifo_count;
    wire can_input=pipe_resetn && enable && pending_valid && !snapshot_valid && in_ready &&
        (!frame_busy || frame_inputs<frame_total);
    wire write_input=wr_valid && !wr_error && wr_addr==PSPL_R_INPUT;
    wire read_output=rd_valid && !rd_error && rd_addr==PSPL_R_OUTPUT;
    wire control_write=wr_valid && !wr_error && wr_addr==PSPL_R_CONTROL;
    wire config_commit=control_write && wr_data[3];
    wire snapshot_ack=control_write && wr_data[4];
    vg_sync_fifo #(.WIDTH(32),.DEPTH(16)) ingress (
        .clk(clk),.rst_n(pipe_resetn),.s_data(wr_data),.s_valid(write_input),.s_ready(in_ready),
        .m_data(in_word),.m_valid(in_valid),.m_ready(in_take),.count(in_fifo_count)
    );
    wire [31:0] affine_data;
    wire affine_valid,affine_ready,affine_sof,affine_eol,affine_clip;
    vg_rgb_affine_axis affine (
        .clk(clk),.rst_n(pipe_resetn),
        .cfg_gain_r(active[2][10:0]),.cfg_gain_g(active[3][10:0]),.cfg_gain_b(active[4][10:0]),
        .cfg_bias_r(active[5]),.cfg_bias_g(active[6]),.cfg_bias_b(active[7]),.cfg_bypass(active_bypass),
        .s_axis_tdata({8'b0,in_word[23:0]}),.s_axis_tvalid(in_valid),.s_axis_tready(in_take),
        .s_axis_tuser(in_word[24]),.s_axis_tlast(in_word[25]),
        .m_axis_tdata(affine_data),.m_axis_tvalid(affine_valid),.m_axis_tready(affine_ready),
        .m_axis_tuser(affine_sof),.m_axis_tlast(affine_eol),.m_axis_clip(affine_clip)
    );
    wire [31:0] hsv_data;
    wire hsv_valid,hsv_ready,hsv_sof,hsv_eol;
    vg_hsv_mask_axis hsv (
        .clk(clk),.rst_n(pipe_resetn),.cfg_min_hsv(active[8][23:0]),.cfg_max_hsv(active[9][23:0]),
        .s_axis_tdata(affine_data),.s_axis_tvalid(affine_valid),.s_axis_tready(affine_ready),
        .s_axis_tuser(affine_sof),.s_axis_tlast(affine_eol),
        .m_axis_tdata(hsv_data),.m_axis_tvalid(hsv_valid),.m_axis_tready(hsv_ready),
        .m_axis_tuser(hsv_sof),.m_axis_tlast(hsv_eol)
    );
    wire [33:0] egress_word;
    wire egress_valid,egress_ready;
    wire [4:0] out_fifo_count;
    vg_sync_fifo #(.WIDTH(34),.DEPTH(16)) egress (
        .clk(clk),.rst_n(pipe_resetn),.s_data({hsv_sof,hsv_eol,hsv_data}),
        .s_valid(hsv_valid),.s_ready(hsv_ready),.m_data(egress_word),
        .m_valid(egress_valid),.m_ready(egress_ready),.count(out_fifo_count)
    );
    wire [31:0] result_data,count;
    wire result_valid,result_sof,result_eol,stats_done,stats_frame_valid;
    wire [15:0] xmin,ymin,xmax,ymax;
    wire [63:0] sum_x,sum_y;
    vg_roi_moments_axis moments (
        .clk(clk),.rst_n(pipe_resetn),.cfg_width(active[0][15:0]),.cfg_height(active[1][15:0]),
        .cfg_xmin(active[10][15:0]),.cfg_ymin(active[11][15:0]),
        .cfg_xmax(active[12][15:0]),.cfg_ymax(active[13][15:0]),.source_error(frame_error),
        .s_axis_tdata(egress_word[31:0]),.s_axis_tvalid(egress_valid),.s_axis_tready(egress_ready),
        .s_axis_tuser(egress_word[33]),.s_axis_tlast(egress_word[32]),
        .m_axis_tdata(result_data),.m_axis_tvalid(result_valid),.m_axis_tready(read_output),
        .m_axis_tuser(result_sof),.m_axis_tlast(result_eol),
        .done(stats_done),.frame_valid(stats_frame_valid),.result_count(count),
        .result_xmin(xmin),.result_ymin(ymin),.result_xmax(xmax),.result_ymax(ymax),
        .result_sum_x(sum_x),.result_sum_y(sum_y)
    );
    // Full-word stores only. Partial WSTRB produces SLVERR and no side effect;
    // unaligned addresses are rejected by vg_axil_regs before reaching this map.
    always @* begin
        wr_error=0;
        if(wr_strb!=4'hf)wr_error=1;
        else if(wr_addr>=PSPL_V_WIDTH && wr_addr<=PSPL_V_CONFIG_ID)begin end
        else case(wr_addr)
            PSPL_R_CONTROL:begin
                if(wr_data[31:5]!=0)wr_error=1;
                if(wr_data[2] && wr_data!=32'd4)wr_error=1;
                if(frame_busy && !wr_data[0] && !wr_data[2])wr_error=1;
                if(wr_data[3] && !stage_ok)wr_error=1;
                if(wr_data[4] && !snapshot_valid)wr_error=1;
            end
            PSPL_R_ERROR:begin end
            PSPL_R_INPUT:if(!can_input || wr_data[31:26]!=0 || (!frame_busy && !wr_data[24]))wr_error=1;
            default:wr_error=1;
        endcase
    end
    always @* begin
        rd_error=0;rd_data=0;
        if(rd_addr>=PSPL_V_WIDTH && rd_addr<=PSPL_V_CONFIG_ID)rd_data=stage[(rd_addr-PSPL_V_WIDTH)>>2];
        else case(rd_addr)
            PSPL_R_ID:rd_data=32'h56475632;
            PSPL_R_VERSION:rd_data=1;
            PSPL_R_CAPABILITIES:rd_data=32'h0000000f; // RGB affine, HSV, ROI moments, PIO
            PSPL_R_CONTROL:rd_data={30'b0,bypass_control,enable};
            PSPL_R_STATUS:rd_data={27'b0,snapshot_valid,pending_valid,frame_busy,result_valid,can_input};
            PSPL_R_ERROR:rd_data=errors;
            PSPL_R_IN_COUNT:rd_data=input_count;
            PSPL_R_OUT_COUNT:rd_data=output_count;
            PSPL_R_OUTPUT:begin
                rd_data={5'b0,result_data[31],result_eol,result_sof,result_data[23:0]};
                if(!result_valid)begin rd_error=1;rd_data=0;end
            end
            PSPL_R_CONFIG_VERSION:rd_data=active[14];
            PSPL_R_COMPLETE:rd_data=completed;
            PSPL_V_FRAME:rd_data=snapshot_frame;
            PSPL_V_COUNT:rd_data=count;
            PSPL_V_XMIN:rd_data={16'b0,xmin};
            PSPL_V_YMIN:rd_data={16'b0,ymin};
            PSPL_V_XMAX:rd_data={16'b0,xmax};
            PSPL_V_YMAX:rd_data={16'b0,ymax};
            PSPL_V_SUM_X_LO:rd_data=sum_x[31:0];PSPL_V_SUM_X_HI:rd_data=sum_x[63:32];
            PSPL_V_SUM_Y_LO:rd_data=sum_y[31:0];PSPL_V_SUM_Y_HI:rd_data=sum_y[63:32];
            PSPL_V_VALID:rd_data={30'b0,(count!=0 && snapshot_valid),
                (stats_frame_valid && !frame_error && snapshot_valid)};
            PSPL_V_CLIP_COUNT:rd_data=clip_count;
            default:rd_error=1;
        endcase
    end
    wire malformed_input=write_input && (wr_data[24]!=(frame_inputs==0) ||
        wr_data[25]!=(in_x==(frame_busy ? active[0] : pending[0])-1'b1));
    reg [31:0] errors_next;
    always @* begin
        // W1C precedes new events: a simultaneous new error is never erased.
        errors_next=errors;
        if(wr_valid && !wr_error && wr_addr==PSPL_R_ERROR)
            errors_next=errors_next & ~wr_data;
        if(wr_valid && wr_error)begin
            if(wr_addr==PSPL_R_INPUT)errors_next=errors_next|32'h00000004;
            else if(wr_addr==PSPL_R_CONTROL && wr_data[3])errors_next=errors_next|32'h00000001;
            else errors_next=errors_next|32'h00000010;
        end
        if(rd_valid && rd_error)
            errors_next=errors_next|(rd_addr==PSPL_R_OUTPUT ? 32'h8 : 32'h10);
        if(malformed_input || (stats_done && (!stats_frame_valid || frame_error)))
            errors_next=errors_next|32'h00000002;
    end
    integer i;
    always @(posedge clk)begin
        if(!rst_n)begin
            enable<=0;bypass_control<=0;soft_reset<=0;
            pending_valid<=0;pending_bypass<=0;active_bypass<=0;
            frame_busy<=0;snapshot_valid<=0;frame_error<=0;
            errors<=0;input_count<=0;output_count<=0;completed<=0;snapshot_frame<=0;clip_count<=0;
            frame_inputs<=0;in_x<=0;in_y<=0;
            for(i=0;i<15;i=i+1)begin stage[i]<=0;pending[i]<=0;active[i]<=0;end
            stage[0]<=640;stage[1]<=360;stage[2]<=256;stage[3]<=256;stage[4]<=256;
            stage[9]<=32'h00ffffb3;stage[12]<=639;stage[13]<=359;
        end else if(soft_reset)begin
            // Session reset discards pending frames/FIFOs; staging survives.
            enable<=0;bypass_control<=0;soft_reset<=0;pending_valid<=0;
            frame_busy<=0;snapshot_valid<=0;frame_error<=0;errors<=0;
            input_count<=0;output_count<=0;completed<=0;snapshot_frame<=0;clip_count<=0;
            frame_inputs<=0;in_x<=0;in_y<=0;
        end else begin
            soft_reset<=0;
            errors<=errors_next;
            if(affine_valid && affine_ready && affine_clip && clip_count!=32'hffffffff)
                clip_count<=clip_count+1'b1;
            if(wr_valid && !wr_error)begin
                if(wr_addr>=PSPL_V_WIDTH && wr_addr<=PSPL_V_CONFIG_ID)stage[(wr_addr-PSPL_V_WIDTH)>>2]<=wr_data;
            end
            if(control_write)begin
                enable<=wr_data[0];bypass_control<=wr_data[1];
                if(wr_data[2])soft_reset<=1;
            end
            if(config_commit)begin
                for(i=0;i<15;i=i+1)pending[i]<=stage[i];
                pending_valid<=1;pending_bypass<=wr_data[1];
            end
            if(snapshot_ack)begin
                snapshot_valid<=0;frame_busy<=0;frame_inputs<=0;frame_error<=0;in_x<=0;in_y<=0;
            end
            if(write_input)begin
                input_count<=input_count+1'b1;frame_inputs<=frame_inputs+1'b1;
                if(!frame_busy)begin
                    // A concurrent CONFIG_COMMIT cannot overtake this SOF:
                    // pending[] here is the previous committed configuration.
                    for(i=0;i<15;i=i+1)active[i]<=pending[i];
                    active_bypass<=pending_bypass;frame_busy<=1;
                end
                if(malformed_input)frame_error<=1;
                if(in_x==(frame_busy ? active[0] : pending[0])-1'b1)begin in_x<=0;in_y<=in_y+1'b1;end
                else in_x<=in_x+1'b1;
            end
            if(read_output)output_count<=output_count+1'b1;
            if(stats_done)begin
                snapshot_valid<=1;completed<=completed+1'b1;snapshot_frame<=completed+1'b1;
            end
        end
    end
endmodule
