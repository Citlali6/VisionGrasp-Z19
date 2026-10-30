// SPDX-License-Identifier: Apache-2.0
// The six-cycle free-running arithmetic is the pinned, unmodified MIT laperex
// cv_rgb_to_hsv core in color_locator/vendor/laperex. Credit reservation follows
// vg_color_axis; tags advance EVERY cycle, including bubbles and downstream stall.
// General HSV bounds are the new profile's contract. RGB is never highlighted.
module vg_hsv_mask_axis #(parameter integer FIFO_DEPTH=16) (
    input wire clk, input wire rst_n,
    input wire [23:0] cfg_min_hsv, cfg_max_hsv,
    input wire [31:0] s_axis_tdata,
    input wire s_axis_tvalid, output wire s_axis_tready,
    input wire s_axis_tuser, s_axis_tlast,
    output wire [31:0] m_axis_tdata,
    output wire m_axis_tvalid, input wire m_axis_tready,
    output wire m_axis_tuser, m_axis_tlast
);
    localparam integer LATENCY=6;
    localparam integer CW=$clog2(FIFO_DEPTH+1);
    reg [CW-1:0] outstanding;
    wire take_out=m_axis_tvalid && m_axis_tready;
    wire take_in=s_axis_tvalid && s_axis_tready;
    assign s_axis_tready=rst_n && (outstanding<FIFO_DEPTH || take_out);
    reg started;
    reg [23:0] frame_min, frame_max;
    reg [23:0] rgb_delay[0:LATENCY-1];
    reg [23:0] min_delay[0:LATENCY-1],max_delay[0:LATENCY-1];
    reg sof_delay[0:LATENCY-1],enabled_delay[0:LATENCY-1];
    cv_pkt_pkg::pkt_hsv hsv;
    wire hsv_valid,hsv_last;
    cv_rgb_to_hsv converter (
        .aclk(clk),.aresetn(rst_n),.in(s_axis_tdata[23:0]),
        .s_tvalid(take_in),.s_tlast(s_axis_tlast && take_in),
        .out(hsv),.m_tvalid(hsv_valid),.m_tlast(hsv_last)
    );
    wire [23:0] lo=min_delay[LATENCY-1],hi=max_delay[LATENCY-1];
    wire hue_match=lo[7:0]<=hi[7:0] ?
        (hsv.h>=lo[7:0] && hsv.h<=hi[7:0]) :
        (hsv.h>=lo[7:0] || hsv.h<=hi[7:0]);
    wire mask=enabled_delay[LATENCY-1] && hue_match &&
        hsv.s>=lo[15:8] && hsv.s<=hi[15:8] &&
        hsv.v>=lo[23:16] && hsv.v<=hi[23:16];
    wire [33:0] fifo_data;
    wire fifo_ready;
    wire [CW-1:0] fifo_count;
    vg_sync_fifo #(.WIDTH(34),.DEPTH(FIFO_DEPTH)) results (
        .clk(clk),.rst_n(rst_n),
        .s_data({sof_delay[LATENCY-1],hsv_last,mask,7'b0,rgb_delay[LATENCY-1]}),
        .s_valid(hsv_valid),.s_ready(fifo_ready),
        .m_data(fifo_data),.m_valid(m_axis_tvalid),.m_ready(m_axis_tready),.count(fifo_count)
    );
    assign {m_axis_tuser,m_axis_tlast,m_axis_tdata}=fifo_data;
    // fifo_ready is guaranteed by the outstanding-credit invariant: every core
    // input reserves space until its output is consumed, not merely produced.
    integer i;
    always @(posedge clk) begin
        if(!rst_n) begin
            outstanding<=0;started<=0;frame_min<=0;frame_max<=24'hffffb3;
            for(i=0;i<LATENCY;i=i+1) begin
                rgb_delay[i]<=0;min_delay[i]<=0;max_delay[i]<=0;
                sof_delay[i]<=0;enabled_delay[i]<=0;
            end
        end else begin
            case({take_in,take_out})
                2'b10:outstanding<=outstanding+1'b1;
                2'b01:outstanding<=outstanding-1'b1;
                default:;
            endcase
            if(take_in && s_axis_tuser) begin
                started<=1;frame_min<=cfg_min_hsv;frame_max<=cfg_max_hsv;
            end
            rgb_delay[0]<=s_axis_tdata[23:0];
            sof_delay[0]<=take_in && s_axis_tuser;
            enabled_delay[0]<=started || (take_in && s_axis_tuser);
            min_delay[0]<=take_in && s_axis_tuser ? cfg_min_hsv : frame_min;
            max_delay[0]<=take_in && s_axis_tuser ? cfg_max_hsv : frame_max;
            for(i=1;i<LATENCY;i=i+1) begin
                rgb_delay[i]<=rgb_delay[i-1];sof_delay[i]<=sof_delay[i-1];
                enabled_delay[i]<=enabled_delay[i-1];
                min_delay[i]<=min_delay[i-1];max_delay[i]<=max_delay[i-1];
            end
        end
    end
endmodule
