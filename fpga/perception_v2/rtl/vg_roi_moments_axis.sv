// SPDX-License-Identifier: Apache-2.0
// Transparent stream tap. Statistics advance on downstream CONSUMPTION only.
// ROI is inclusive and does not crop pixels. For width,height <=4096:
// count<=2^24; sum_x,sum_y<=2^24*4095<2^36, safely inside 64 bits.
module vg_roi_moments_axis (
    input wire clk, input wire rst_n,
    input wire [15:0] cfg_width,cfg_height,
    input wire [15:0] cfg_xmin,cfg_ymin,cfg_xmax,cfg_ymax,
    input wire source_error,
    input wire [31:0] s_axis_tdata,
    input wire s_axis_tvalid, output wire s_axis_tready,
    input wire s_axis_tuser,s_axis_tlast,
    output wire [31:0] m_axis_tdata,
    output wire m_axis_tvalid, input wire m_axis_tready,
    output wire m_axis_tuser,m_axis_tlast,
    output reg done, output reg frame_valid,
    output reg [31:0] result_count,
    output reg [15:0] result_xmin,result_ymin,result_xmax,result_ymax,
    output reg [63:0] result_sum_x,result_sum_y
);
    assign m_axis_tdata=s_axis_tdata;
    assign m_axis_tvalid=s_axis_tvalid && rst_n;
    assign m_axis_tuser=s_axis_tuser;
    assign m_axis_tlast=s_axis_tlast;
    assign s_axis_tready=m_axis_tready && rst_n;
    wire take=s_axis_tvalid && s_axis_tready;
    reg started,invalid;
    reg [31:0] index,count;
    reg [15:0] x,y,xmin,ymin,xmax,ymax;
    reg [63:0] sum_x,sum_y;
    wire first=!started && s_axis_tuser;
    wire [15:0] px=first ? 16'b0 : x;
    wire [15:0] py=first ? 16'b0 : y;
    wire [31:0] pi=first ? 32'b0 : index;
    wire [31:0] total={16'b0,cfg_width}*{16'b0,cfg_height};
    wire malformed=(s_axis_tuser != first) ||
        (s_axis_tlast != (px==cfg_width-1'b1)) || py>=cfg_height;
    wire selected=s_axis_tdata[31] && px>=cfg_xmin && px<=cfg_xmax &&
        py>=cfg_ymin && py<=cfg_ymax;
    reg [31:0] next_count;
    reg [63:0] next_sum_x,next_sum_y;
    reg [15:0] next_xmin,next_ymin,next_xmax,next_ymax;
    always @* begin
        next_count=first ? 0 : count;
        next_sum_x=first ? 0 : sum_x;next_sum_y=first ? 0 : sum_y;
        next_xmin=first ? 16'hffff : xmin;next_ymin=first ? 16'hffff : ymin;
        next_xmax=first ? 0 : xmax;next_ymax=first ? 0 : ymax;
        if(selected) begin
            next_count=next_count+1'b1;
            next_sum_x=next_sum_x+{48'b0,px};
            next_sum_y=next_sum_y+{48'b0,py};
            if(px<next_xmin)next_xmin=px;if(px>next_xmax)next_xmax=px;
            if(py<next_ymin)next_ymin=py;if(py>next_ymax)next_ymax=py;
        end
    end
    always @(posedge clk) begin
        if(!rst_n) begin
            started<=0;invalid<=0;index<=0;x<=0;y<=0;
            count<=0;sum_x<=0;sum_y<=0;xmin<=0;ymin<=0;xmax<=0;ymax<=0;
            done<=0;frame_valid<=0;result_count<=0;
            result_xmin<=0;result_ymin<=0;result_xmax<=0;result_ymax<=0;
            result_sum_x<=0;result_sum_y<=0;
        end else begin
            done<=0;
            if(take && (started || first)) begin
                started<=1;
                invalid<=(first ? 1'b0 : invalid) || malformed;
                count<=next_count;sum_x<=next_sum_x;sum_y<=next_sum_y;
                xmin<=next_xmin;ymin<=next_ymin;xmax<=next_xmax;ymax<=next_ymax;
                index<=pi+1'b1;
                if(px==cfg_width-1'b1)begin x<=0;y<=py+1'b1;end
                else begin x<=px+1'b1;y<=py;end
                if(pi==total-1'b1)begin
                    done<=1;started<=0;
                    // All next_* values include the FINAL consumed pixel.
                    frame_valid<=!(source_error || malformed || (!first && invalid));
                    result_count<=next_count;
                    result_sum_x<=next_sum_x;result_sum_y<=next_sum_y;
                    result_xmin<=next_count==0 ? 0 : next_xmin;
                    result_ymin<=next_count==0 ? 0 : next_ymin;
                    result_xmax<=next_count==0 ? 0 : next_xmax;
                    result_ymax<=next_count==0 ? 0 : next_ymax;
                end
            end
        end
    end
endmodule
