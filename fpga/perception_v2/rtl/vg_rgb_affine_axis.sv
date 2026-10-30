// SPDX-License-Identifier: Apache-2.0
// One elastic register; the accepted SOF uses incoming parameters immediately.
module vg_rgb_affine_axis (
    input wire clk, input wire rst_n,
    input wire [10:0] cfg_gain_r, cfg_gain_g, cfg_gain_b,
    input wire signed [31:0] cfg_bias_r, cfg_bias_g, cfg_bias_b,
    input wire cfg_bypass,
    input wire [31:0] s_axis_tdata,
    input wire s_axis_tvalid, output wire s_axis_tready,
    input wire s_axis_tuser, s_axis_tlast,
    output reg [31:0] m_axis_tdata,
    output reg m_axis_tvalid, input wire m_axis_tready,
    output reg m_axis_tuser, m_axis_tlast,
    output reg m_axis_clip
);
    reg [10:0] gain_r, gain_g, gain_b;
    reg signed [31:0] bias_r, bias_g, bias_b;
    reg bypass;
    function automatic [8:0] channel;
        input [7:0] pixel;
        input [10:0] gain;
        input signed [31:0] bias;
        reg [18:0] product;
        reg [19:0] rounded;
        reg signed [32:0] scaled, adjusted;
        begin
            // Nonnegative product <=255*1024=261120; round BEFORE bias.
            product = {11'b0,pixel} * {8'b0,gain};
            rounded = {1'b0,product} + 20'd128;
            scaled = $signed({1'b0,rounded[19:8]});
            adjusted = scaled + $signed({bias[31],bias});
            if (adjusted < 33'sd0) channel = {1'b1,8'd0};
            else if (adjusted > 33'sd255) channel = {1'b1,8'd255};
            else channel = {1'b0,adjusted[7:0]};
        end
    endfunction
    wire use_bypass = s_axis_tuser ? cfg_bypass : bypass;
    wire [8:0] red = channel(s_axis_tdata[23:16],
        s_axis_tuser ? cfg_gain_r : gain_r, s_axis_tuser ? cfg_bias_r : bias_r);
    wire [8:0] green = channel(s_axis_tdata[15:8],
        s_axis_tuser ? cfg_gain_g : gain_g, s_axis_tuser ? cfg_bias_g : bias_g);
    wire [8:0] blue = channel(s_axis_tdata[7:0],
        s_axis_tuser ? cfg_gain_b : gain_b, s_axis_tuser ? cfg_bias_b : bias_b);
    assign s_axis_tready = rst_n && (!m_axis_tvalid || m_axis_tready);
    always @(posedge clk) begin
        if (!rst_n) begin
            gain_r <= 256; gain_g <= 256; gain_b <= 256;
            bias_r <= 0; bias_g <= 0; bias_b <= 0; bypass <= 0;
            m_axis_tvalid <= 0; m_axis_tdata <= 0;
            m_axis_tuser <= 0; m_axis_tlast <= 0; m_axis_clip <= 0;
        end else if (s_axis_tready) begin
            m_axis_tvalid <= s_axis_tvalid;
            if (s_axis_tvalid) begin
                m_axis_tuser <= s_axis_tuser;
                m_axis_tlast <= s_axis_tlast;
                m_axis_clip <= !use_bypass && (red[8] || green[8] || blue[8]);
                m_axis_tdata <= {8'b0,
                    use_bypass ? s_axis_tdata[23:16] : red[7:0],
                    use_bypass ? s_axis_tdata[15:8] : green[7:0],
                    use_bypass ? s_axis_tdata[7:0] : blue[7:0]};
                if (s_axis_tuser) begin
                    gain_r <= cfg_gain_r; gain_g <= cfg_gain_g; gain_b <= cfg_gain_b;
                    bias_r <= cfg_bias_r; bias_g <= cfg_bias_g; bias_b <= cfg_bias_b;
                    bypass <= cfg_bypass;
                end
            end
        end
    end
endmodule
