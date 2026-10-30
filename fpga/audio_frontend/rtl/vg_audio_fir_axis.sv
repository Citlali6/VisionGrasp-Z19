// SPDX-License-Identifier: Apache-2.0
// 63-tap Q1.15 FIR; one signed multiplier and a 48-bit MAC accumulator.
// Coefficients are immutable while work is in flight (enforced by AXI wrapper).
module vg_audio_fir_axis (
    input wire clk, input wire resetn, input wire bypass,
    input wire [1007:0] coefficients,
    input wire signed [15:0] s_data, input wire s_valid, output wire s_ready,
    output reg signed [15:0] m_data, output reg m_valid, input wire m_ready,
    output wire busy, output reg clipped
);
    reg signed [15:0] history [0:62];
    reg [5:0] tap;
    reg computing;
    reg signed [47:0] accumulator;
    wire signed [15:0] coefficient = coefficients[16*tap +: 16];
    wire signed [31:0] product = history[tap] * coefficient;
    wire signed [47:0] sum = accumulator + $signed({{16{product[31]}},product});
    // The magnitude is 49 bits so negation of the most-negative value is defined.
    wire signed [48:0] extended_sum = {sum[47],sum};
    wire signed [48:0] magnitude = extended_sum < 0 ? -extended_sum : extended_sum;
    wire signed [48:0] rounded_magnitude = (magnitude + 49'sd16384) >>> 15;
    wire signed [48:0] rounded = extended_sum < 0 ? -rounded_magnitude : rounded_magnitude;
    assign busy = computing || m_valid;
    assign s_ready = resetn && !computing && (!m_valid || m_ready);
    integer i;
    always @(posedge clk) begin
        if (!resetn) begin
            for (i=0;i<63;i=i+1) history[i] <= 0;
            tap <= 0; computing <= 0; accumulator <= 0;
            m_data <= 0; m_valid <= 0; clipped <= 0;
        end else begin
            clipped <= 0;
            if (m_valid && m_ready) m_valid <= 0;
            if (s_valid && s_ready) begin
                for (i=62;i>0;i=i-1) history[i] <= history[i-1];
                history[0] <= s_data;
                if (bypass) begin m_data <= s_data; m_valid <= 1; end
                else begin computing <= 1; tap <= 0; accumulator <= 0; end
            end
            if (computing) begin
                if (tap == 62) begin
                    computing <= 0; m_valid <= 1;
                    m_data <= rounded > 49'sd32767 ? 16'sh7fff :
                              rounded < -49'sd32768 ? 16'sh8000 : rounded[15:0];
                    clipped <= rounded > 49'sd32767 || rounded < -49'sd32768;
                end else begin accumulator <= sum; tap <= tap + 1'b1; end
            end
        end
    end
endmodule
